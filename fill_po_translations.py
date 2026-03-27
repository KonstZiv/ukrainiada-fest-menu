"""Fill empty .po translations using Google Gemini API.

Source language (uk) gets msgid copied to msgstr — no LLM needed.
Other languages are translated one string at a time for accuracy.

Usage:
    uv run python fill_po_translations.py
    uv run python fill_po_translations.py --lang en       # single language
    uv run python fill_po_translations.py --lang uk       # fill source only
    uv run python fill_po_translations.py --dry-run       # preview without writing
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from decouple import Config, RepositoryEnv
from google import genai

config = Config(RepositoryEnv(".env-dev"))
API_KEY = config("GEMINI_API_KEY").split(",")[0].strip()
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-pro"

# Source language — msgid is already in this language, just copy to msgstr.
SOURCE_LANG = "uk"

LANG_NAMES: dict[str, str] = {
    "en": "English",
    "cnr": "Montenegrin (Crnogorski, Latin script with ś/ź)",
    "hr": "Croatian (Hrvatski)",
    "bs": "Bosnian (Bosanski)",
    "it": "Italian (Italiano)",
    "de": "German (Deutsch)",
}

ALL_LANGUAGES = [SOURCE_LANG, *LANG_NAMES]
LOCALE_DIR = Path("locale")
PO_LINE_WIDTH = 75


# ---------------------------------------------------------------------------
# .po parsing
# ---------------------------------------------------------------------------


def _extract_msgid(lines: list[str]) -> str:
    """Extract full msgid from block lines.

    Reads everything between msgid and msgstr, strips quotes, concatenates.
    """
    parts: list[str] = []
    in_msgid = False
    for line in lines:
        if line.startswith("msgid "):
            in_msgid = True
            m = re.match(r'msgid "(.*)"', line)
            if m:
                parts.append(m.group(1))
        elif line.startswith("msgstr "):
            break
        elif line.startswith('"') and in_msgid:
            m = re.match(r'"(.*)"', line)
            if m:
                parts.append(m.group(1))
    return "".join(parts)


def _extract_msgstr(lines: list[str]) -> str:
    """Extract full msgstr from block lines."""
    parts: list[str] = []
    in_msgstr = False
    for line in lines:
        if line.startswith("msgstr "):
            in_msgstr = True
            m = re.match(r'msgstr "(.*)"', line)
            if m:
                parts.append(m.group(1))
        elif line.startswith('"') and in_msgstr:
            m = re.match(r'"(.*)"', line)
            if m:
                parts.append(m.group(1))
        elif in_msgstr and not line.startswith('"'):
            break
    return "".join(parts)


def parse_po(path: Path) -> list[dict[str, str]]:
    """Parse .po file into list of {msgid, msgstr, block} entries."""
    content = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", content)

    entries: list[dict[str, str]] = []
    for block in blocks:
        lines = block.strip().split("\n")
        full_msgid = _extract_msgid(lines)
        full_msgstr = _extract_msgstr(lines)

        if not full_msgid:  # skip header block
            continue

        entries.append(
            {
                "msgid": full_msgid,
                "msgstr": full_msgstr,
                "block": block,
            }
        )

    return entries


# ---------------------------------------------------------------------------
# .po writing — multiline aware
# ---------------------------------------------------------------------------


def _wrap_po_string(text: str, max_width: int = PO_LINE_WIDTH) -> list[str]:
    """Split a translated string into .po multiline format.

    Short strings (≤ max_width) → single line: 'msgstr "text"'
    Long strings → multiline:
        msgstr ""
        "part 1 "
        "part 2"

    Splits at word boundaries, preserving spaces.
    """
    if len(text) <= max_width:
        return [text]

    # Split into lines of ≤ max_width at word boundaries.
    lines: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_width:
            lines.append(remaining)
            break

        # Find last space within max_width.
        cut = remaining.rfind(" ", 0, max_width)
        if cut == -1:
            # No space found — force cut at max_width.
            cut = max_width

        # Include the trailing space in this line.
        lines.append(remaining[: cut + 1])
        remaining = remaining[cut + 1 :]

    return lines


def _build_msgstr_block(text: str) -> str:
    """Build a complete msgstr block string for a .po file."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    parts = _wrap_po_string(escaped)

    if len(parts) == 1:
        return f'msgstr "{parts[0]}"'

    # Multiline: msgstr "" followed by quoted lines.
    lines = ['msgstr ""']
    for part in parts:
        lines.append(f'"{part}"')
    return "\n".join(lines)


def fill_po(path: Path, translations: dict[str, str]) -> int:
    """Replace empty msgstr entries in .po file with translations.

    Returns number of entries filled.
    """
    content = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", content)
    lookup = {k: v for k, v in translations.items() if v}
    if not lookup:
        return 0

    new_blocks: list[str] = []
    filled = 0

    for block in blocks:
        lines = block.strip().split("\n")
        full_msgid = _extract_msgid(lines)
        full_msgstr = _extract_msgstr(lines)

        if full_msgid and not full_msgstr and full_msgid in lookup:
            # Rebuild the block: keep everything up to msgstr, replace msgstr.
            pre_msgstr_lines: list[str] = []
            for line in lines:
                pre_msgstr_lines.append(line)
                if line.startswith("msgstr "):
                    break

            # Remove the old msgstr line, keep comments and msgid part.
            pre_msgstr_lines.pop()
            new_msgstr = _build_msgstr_block(lookup[full_msgid])
            block = "\n".join(pre_msgstr_lines) + "\n" + new_msgstr
            filled += 1

        new_blocks.append(block)

    path.write_text("\n\n".join(new_blocks), encoding="utf-8")
    return filled


# ---------------------------------------------------------------------------
# Source language: just copy msgid → msgstr
# ---------------------------------------------------------------------------


def fill_source_language(*, dry_run: bool = False) -> None:
    """Fill source language .po by copying msgid to msgstr (no LLM)."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {SOURCE_LANG} (SOURCE — copy msgid → msgstr)")
    print(f"{'=' * 60}")

    for domain in ["django", "djangojs"]:
        po_path = LOCALE_DIR / SOURCE_LANG / "LC_MESSAGES" / f"{domain}.po"
        if not po_path.exists():
            print(f"  {domain}.po not found, skipping")
            continue

        entries = parse_po(po_path)
        empty = [e for e in entries if not e["msgstr"]]

        if not empty:
            print(f"  {domain}.po — all filled!")
            continue

        print(f"  {domain}.po — {len(empty)} empty strings")

        if dry_run:
            for e in empty[:5]:
                print(f"    [DRY] {e['msgid']!r}")
            if len(empty) > 5:
                print(f"    ... and {len(empty) - 5} more")
            continue

        translations = {e["msgid"]: e["msgid"] for e in empty}
        filled = fill_po(po_path, translations)
        print(f"  Copied {filled} msgid → msgstr")


# ---------------------------------------------------------------------------
# LLM translation: one string at a time
# ---------------------------------------------------------------------------


def translate_single(string: str, lang_code: str) -> str:
    """Translate a single Ukrainian string via Gemini API."""
    lang_name = LANG_NAMES[lang_code]

    prompt = (
        f"Translate this UI string to {lang_name}:\n\n"
        f'"{string}"\n\n'
        "Rules:\n"
        "- Restaurant menu system context (buttons, labels, messages).\n"
        "- Keep %(var)s placeholders exactly as-is.\n"
        "- Keep HTML tags exactly as-is.\n"
        "- Preserve emoji if present.\n"
        "- For Montenegrin (cnr): use Latin script with ś, ź.\n"
        "- Return ONLY the translated string, nothing else.\n"
        "- No quotes, no explanation, no markdown."
    )

    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            break
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1)
                print(
                    f"      Rate limited, waiting {wait}s (attempt {attempt + 1}/5)..."
                )
                time.sleep(wait)
            else:
                print(f"      ERROR: {e}")
                return ""
    else:
        print("      Failed after 5 retries")
        return ""

    result = (response.text or "").strip()
    # Strip surrounding quotes if the model added them.
    if len(result) >= 2 and result[0] == '"' and result[-1] == '"':
        result = result[1:-1]
    return result


def process_language(lang_code: str, *, dry_run: bool = False) -> None:
    """Fill empty translations for one language, one string at a time."""
    lang_name = LANG_NAMES[lang_code]
    print(f"\n{'=' * 60}")
    print(f"Processing: {lang_code} ({lang_name}) — one-by-one")
    print(f"{'=' * 60}")

    for domain in ["django", "djangojs"]:
        po_path = LOCALE_DIR / lang_code / "LC_MESSAGES" / f"{domain}.po"
        if not po_path.exists():
            print(f"  {domain}.po not found, skipping")
            continue

        entries = parse_po(po_path)
        empty = [e for e in entries if not e["msgstr"]]

        if not empty:
            print(f"  {domain}.po — all translated!")
            continue

        total = len(empty)
        print(f"  {domain}.po — {total} empty strings")

        if dry_run:
            for e in empty[:5]:
                print(f"    [DRY] {e['msgid']!r}")
            if total > 5:
                print(f"    ... and {total - 5} more")
            continue

        all_translations: dict[str, str] = {}
        failed = 0

        for i, entry in enumerate(empty, 1):
            msgid = entry["msgid"]
            short = msgid[:50] + ("…" if len(msgid) > 50 else "")
            print(f"    [{i}/{total}] {short!r}")

            result = translate_single(msgid, lang_code)

            if result:
                all_translations[msgid] = result
                print(f"             → {result[:80]}")
            else:
                failed += 1
                print("             → FAILED")

            # Rate limit between API calls.
            if i < total:
                time.sleep(1)

        filled = fill_po(po_path, all_translations)
        print(
            f"  Done: {filled}/{total} translated"
            f"{f', {failed} failed' if failed else ''}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill empty .po translations via Gemini API"
    )
    parser.add_argument(
        "--lang",
        choices=ALL_LANGUAGES,
        help="Process only this language (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be translated without writing",
    )
    args = parser.parse_args()

    languages = [args.lang] if args.lang else ALL_LANGUAGES

    print(f"Model: {MODEL}")
    print(f"Languages: {', '.join(languages)}")
    if args.dry_run:
        print("DRY RUN — no files will be modified\n")

    for lang in languages:
        if lang == SOURCE_LANG:
            fill_source_language(dry_run=args.dry_run)
        else:
            process_language(lang, dry_run=args.dry_run)

    if not args.dry_run:
        # Compile .mo files.
        print(f"\n{'=' * 60}")
        print("Compiling .mo files...")
        import subprocess

        locale_flags = [f"--locale={lang}" for lang in languages]
        subprocess.run(
            ["uv", "run", "python", "manage.py", "compilemessages", *locale_flags],
            check=True,
            capture_output=True,
        )
        print("Done!")


if __name__ == "__main__":
    main()
