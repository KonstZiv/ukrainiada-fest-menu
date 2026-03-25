"""Google Gemini API client for menu/news content translation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString
from django.conf import settings
from google import genai

from translations.constants import ContentKind

logger = logging.getLogger(__name__)

# Language display names for the prompt.
_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "cnr": "Montenegrin (Crnogorski)",
    "hr": "Croatian (Hrvatski)",
    "bs": "Bosnian (Bosanski)",
    "it": "Italian (Italiano)",
    "de": "German (Deutsch)",
}

# Pricing per 1M tokens (USD).
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}

DEFAULT_MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# HTML text extraction / reassembly
# ---------------------------------------------------------------------------


def _extract_texts_from_html(html: str) -> tuple[list[str], BeautifulSoup]:
    """Extract translatable text nodes from HTML.

    Returns a list of text strings and the parsed soup (with placeholders).
    """
    soup = BeautifulSoup(html, "html.parser")
    texts: list[str] = []

    for node in soup.descendants:
        if (
            isinstance(node, NavigableString)
            and node.parent is not None
            and node.parent.name not in ("script", "style", "code", "pre")
        ):
            stripped = node.strip()
            if len(stripped) >= 2:  # skip whitespace-only and single chars
                texts.append(stripped)

    return texts, soup


def _reassemble_html(
    soup: BeautifulSoup,
    original_texts: list[str],
    translated_texts: list[str],
) -> str:
    """Replace original text nodes in soup with translated versions."""
    text_map = dict(zip(original_texts, translated_texts, strict=False))

    for node in list(soup.descendants):
        if (
            isinstance(node, NavigableString)
            and node.parent is not None
            and node.parent.name not in ("script", "style", "code", "pre")
        ):
            stripped = node.strip()
            if stripped in text_map:
                # Preserve surrounding whitespace.
                leading = node[: len(node) - len(node.lstrip())]
                trailing = node[len(node.rstrip()) :]
                node.replace_with(
                    NavigableString(leading + text_map[stripped] + trailing)
                )

    return str(soup)


# ---------------------------------------------------------------------------
# Usage stats
# ---------------------------------------------------------------------------


@dataclass
class UsageStats:
    """Accumulated token usage and cost from Gemini API calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0
    _per_call: list[dict[str, object]] = field(default_factory=list)

    def record(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Record a single API call. Returns cost for this call."""
        self.input_tokens += prompt_tokens
        self.output_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.calls += 1

        pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
        call_cost = (
            prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]
        ) / 1_000_000
        self.cost_usd += call_cost

        self._per_call.append(
            {
                "input": prompt_tokens,
                "output": completion_tokens,
                "cost": call_cost,
                "model": model,
            }
        )
        return call_cost

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"{self.calls} calls, "
            f"{self.input_tokens:,} input + {self.output_tokens:,} output tokens, "
            f"${self.cost_usd:.4f}"
        )


# Global stats accumulator (reset per management command run).
usage_stats = UsageStats()


def reset_stats() -> None:
    """Reset accumulated stats (mutates in place so importers keep the reference)."""
    usage_stats.input_tokens = 0
    usage_stats.output_tokens = 0
    usage_stats.total_tokens = 0
    usage_stats.calls = 0
    usage_stats.cost_usd = 0.0
    usage_stats._per_call.clear()


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_prompt(source: dict[str, str], target_languages: list[str]) -> str:
    """Build translation prompt for Gemini."""
    lang_list = ", ".join(
        f"{code} ({_LANG_NAMES.get(code, code)})" for code in target_languages
    )
    source_json = json.dumps(source, ensure_ascii=False, indent=2)

    cnr_rules = ""
    if "cnr" in target_languages:
        cnr_rules = (
            "- MONTENEGRIN (cnr) specific rules:\n"
            "  * Use Latin script with Montenegrin-specific letters ś and ź.\n"
            "  * ś replaces sj in ijekavian forms: pjeśma, śever, śutra, śesti.\n"
            "  * ź replaces zj: iźelica, poiźdalica.\n"
            "  * Use ijekavian: mlijeko, lijepo, bijelo (not mleko, lepo, belo).\n"
            "  * Montenegrin vocabulary: hljeb (bread), kahva (coffee), śutra (tomorrow).\n"
            "  * NOT every s→ś or z→ź — only in specific Montenegrin words.\n"
        )

    return (
        "You are a professional translator for a cultural center website.\n"
        f"Translate the following content from Ukrainian to: {lang_list}.\n\n"
        f"Source (Ukrainian):\n{source_json}\n\n"
        "Rules:\n"
        "- Keep translations natural, appetizing, and culturally appropriate.\n"
        "- Preserve the original meaning.\n"
        f"{cnr_rules}"
        "- Return ONLY valid JSON — no markdown fences, no explanation.\n\n"
        "Expected JSON format:\n"
        '{"en": {"title": "...", "description": "..."}, '
        '"cnr": {"title": "...", "description": "..."}, ...}\n\n'
        "Include all requested languages. Field keys must match the source exactly."
    )


def _extract_json(text: str) -> dict[str, dict[str, str]]:
    """Extract JSON from Gemini response, handling markdown fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    return json.loads(cleaned)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Main translation function
# ---------------------------------------------------------------------------


def translate_with_gemini(
    source: dict[str, str],
    target_languages: list[str],
    model: str = DEFAULT_MODEL,
    field_kinds: dict[str, ContentKind] | None = None,
) -> dict[str, dict[str, str]]:
    """Translate source fields to all target languages in one API call.

    For fields with kind="html", text is extracted from HTML, translated
    as plain text, then reassembled back into the original HTML structure.

    Args:
        source: Field names to Ukrainian text.
        target_languages: Language codes.
        model: Gemini model to use.
        field_kinds: Mapping of field_name -> "plain" | "html".
            If None, all fields are treated as plain text.

    Returns:
        Nested dict: {lang_code: {field_name: translated_text}}.

    """
    api_key: str = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    kinds = field_kinds or {}

    # Separate HTML fields: extract text, translate as plain, reassemble.
    html_meta: dict[str, tuple[list[str], BeautifulSoup]] = {}
    plain_source: dict[str, str] = {}

    for field_name, value in source.items():
        kind = kinds.get(field_name, "plain")
        if kind == "html" and "<" in value:
            texts, soup = _extract_texts_from_html(value)
            if texts:
                html_meta[field_name] = (texts, soup)
                # Send extracted texts as numbered dict for translation.
                for i, txt in enumerate(texts):
                    plain_source[f"_html_{field_name}_{i}"] = txt
            else:
                # No translatable text in HTML — skip field.
                plain_source[field_name] = value
        else:
            plain_source[field_name] = value

    if not plain_source:
        return {}

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(plain_source, target_languages)

    logger.info(
        "Calling Gemini (%s) for %d fields -> %d languages (HTML fields: %s)",
        model,
        len(plain_source),
        len(target_languages),
        list(html_meta.keys()) or "none",
    )

    response = client.models.generate_content(model=model, contents=prompt)

    # Track usage.
    meta = response.usage_metadata
    if meta:
        cost = usage_stats.record(
            prompt_tokens=meta.prompt_token_count or 0,
            completion_tokens=meta.candidates_token_count or 0,
            model=model,
        )
        logger.info(
            "Gemini usage: %d in + %d out tokens, $%.6f this call",
            meta.prompt_token_count or 0,
            meta.candidates_token_count or 0,
            cost,
        )

    raw_text = response.text or ""
    logger.debug("Gemini raw response: %s", raw_text[:500])

    try:
        raw_result = _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Gemini response: %s", raw_text[:500])
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc

    # Reassemble HTML fields from translated text fragments.
    result: dict[str, dict[str, str]] = {}
    for lang, field_data in raw_result.items():
        if lang not in target_languages:
            continue
        lang_fields: dict[str, str] = {}
        for field_name, value in field_data.items():
            if field_name.startswith("_html_"):
                continue  # skip raw fragments — handled below
            lang_fields[field_name] = value
        result[lang] = lang_fields

    # Reassemble HTML for each language.
    for field_name, (original_texts, soup) in html_meta.items():
        for lang in target_languages:
            lang_data = raw_result.get(lang, {})
            translated_texts: list[str] = []
            for i in range(len(original_texts)):
                key = f"_html_{field_name}_{i}"
                translated = lang_data.get(key, original_texts[i])
                translated_texts.append(translated)

            # Reassemble: clone soup for each language.
            lang_soup = BeautifulSoup(str(soup), "html.parser")
            html_result = _reassemble_html(lang_soup, original_texts, translated_texts)
            result.setdefault(lang, {})[field_name] = html_result

    # Validate: ensure all requested languages present.
    missing = set(target_languages) - set(result.keys())
    if missing:
        logger.warning("Gemini response missing languages: %s", missing)

    return result
