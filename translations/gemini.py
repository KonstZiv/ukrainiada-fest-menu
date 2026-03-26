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


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from Gemini response."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    return re.sub(r"```\s*$", "", cleaned).strip()


def _extract_json(text: str) -> dict[str, dict[str, str]]:
    """Extract nested JSON from Gemini translation response."""
    return json.loads(_strip_markdown_fences(text))  # type: ignore[no-any-return]


def _extract_flat_json(text: str) -> dict[str, object]:
    """Extract flat JSON from Gemini review/correction response."""
    return json.loads(_strip_markdown_fences(text))  # type: ignore[no-any-return]


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


# ---------------------------------------------------------------------------
# Review scores dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReviewScores:
    """LLM reviewer evaluation of a single-language translation."""

    accuracy: float = 0.0
    emotion: float = 0.0
    quality: float = 0.0
    style: float = 0.0
    grammar: float = 0.0
    ethics: float = 0.0
    comment: str = ""

    @property
    def average(self) -> float:
        scores = [
            self.accuracy,
            self.emotion,
            self.quality,
            self.style,
            self.grammar,
            self.ethics,
        ]
        return sum(scores) / len(scores)

    @property
    def passed(self) -> bool:
        return self.average >= REVIEW_THRESHOLD


# Review threshold — translations below this average go back for correction.
REVIEW_THRESHOLD: float = 8.5

# Max correction iterations to avoid infinite loops.
MAX_CORRECTION_ITERATIONS: int = 2

# Roles: translator = fast/cheap, reviewer = smart/accurate.
TRANSLATOR_MODEL = "gemini-2.5-flash"
REVIEWER_MODEL = "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Reviewer — evaluates a translation and returns scores
# ---------------------------------------------------------------------------


def _build_review_prompt(
    source: dict[str, str],
    translation: dict[str, str],
    lang_code: str,
) -> str:
    """Build a prompt for the LLM reviewer role."""
    lang_name = _LANG_NAMES.get(lang_code, lang_code)
    source_json = json.dumps(source, ensure_ascii=False, indent=2)
    translation_json = json.dumps(translation, ensure_ascii=False, indent=2)

    return (
        "You are an expert linguistic reviewer who deeply understands Ukrainian "
        "culture, language nuances, and their expression in other languages.\n\n"
        f"Evaluate this Ukrainian → {lang_name} translation.\n\n"
        f"Original (Ukrainian):\n{source_json}\n\n"
        f"Translation ({lang_name}):\n{translation_json}\n\n"
        "Rate each criterion from 0.0 to 10.0:\n"
        "- accuracy: faithfulness to the original meaning\n"
        "- emotion: preservation of emotional tone and connotation\n"
        "- quality: overall translation quality\n"
        "- style: stylistic naturalness in the target language\n"
        "- grammar: grammatical correctness in the target language\n"
        "- ethics: cultural and ethical appropriateness\n\n"
        "If any score is below 9, provide a brief 'comment' explaining what "
        "should be improved — this will be sent back to the translator.\n\n"
        "Return ONLY valid JSON, no markdown fences:\n"
        '{"accuracy": 9.0, "emotion": 8.5, "quality": 9.0, '
        '"style": 8.0, "grammar": 9.5, "ethics": 10.0, '
        '"comment": "..."}'
    )


def review_translation(
    source: dict[str, str],
    translation: dict[str, str],
    lang_code: str,
    model: str = REVIEWER_MODEL,
) -> ReviewScores:
    """Have the LLM reviewer evaluate a translation for one language.

    Args:
        source: Original Ukrainian field values.
        translation: Translated field values for one language.
        lang_code: Target language code.
        model: Gemini model for review (default: pro).

    Returns:
        ReviewScores with individual scores and comment.

    """
    api_key: str = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    prompt = _build_review_prompt(source, translation, lang_code)

    lang_name = _LANG_NAMES.get(lang_code, lang_code)
    logger.info("Reviewing %s translation with %s", lang_name, model)

    response = client.models.generate_content(model=model, contents=prompt)

    meta = response.usage_metadata
    if meta:
        usage_stats.record(
            prompt_tokens=meta.prompt_token_count or 0,
            completion_tokens=meta.candidates_token_count or 0,
            model=model,
        )

    raw_text = response.text or ""
    try:
        data = _extract_flat_json(raw_text)
    except json.JSONDecodeError, ValueError:
        logger.error("Failed to parse review response: %s", raw_text[:300])
        # Return passing scores on parse failure — don't block translation.
        return ReviewScores(
            accuracy=10,
            emotion=10,
            quality=10,
            style=10,
            grammar=10,
            ethics=10,
            comment="[review parse error — auto-passed]",
        )

    return ReviewScores(
        accuracy=float(data.get("accuracy", 0)),  # type: ignore[arg-type]
        emotion=float(data.get("emotion", 0)),  # type: ignore[arg-type]
        quality=float(data.get("quality", 0)),  # type: ignore[arg-type]
        style=float(data.get("style", 0)),  # type: ignore[arg-type]
        grammar=float(data.get("grammar", 0)),  # type: ignore[arg-type]
        ethics=float(data.get("ethics", 0)),  # type: ignore[arg-type]
        comment=str(data.get("comment", "")),
    )


# ---------------------------------------------------------------------------
# Correction — re-translate with reviewer feedback
# ---------------------------------------------------------------------------


def _build_correction_prompt(
    source: dict[str, str],
    previous_translation: dict[str, str],
    lang_code: str,
    reviewer_comment: str,
) -> str:
    """Build a prompt for the translator to fix based on reviewer feedback."""
    lang_name = _LANG_NAMES.get(lang_code, lang_code)
    source_json = json.dumps(source, ensure_ascii=False, indent=2)
    prev_json = json.dumps(previous_translation, ensure_ascii=False, indent=2)

    cnr_rules = ""
    if lang_code == "cnr":
        cnr_rules = (
            "- MONTENEGRIN specific: use Latin script with ś/ź.\n"
            "  ś replaces sj in ijekavian: pjeśma, śever, śutra.\n"
            "  ź replaces zj: iźelica, poiźdalica.\n"
            "  Use ijekavian: mlijeko, lijepo, bijelo.\n"
        )

    return (
        "You are a professional polyglot translator who knows Ukrainian deeply "
        "and translates with cultural sensitivity.\n\n"
        f"Your previous Ukrainian → {lang_name} translation was reviewed. "
        "Please provide an improved translation based on the feedback.\n\n"
        f"Original (Ukrainian):\n{source_json}\n\n"
        f"Your previous translation:\n{prev_json}\n\n"
        f"Reviewer feedback:\n{reviewer_comment}\n\n"
        "Rules:\n"
        "- Fix ONLY the issues mentioned in the feedback.\n"
        "- Keep everything else unchanged.\n"
        f"{cnr_rules}"
        "- Return ONLY valid JSON with the corrected translation.\n"
        "- Same keys as the original, no markdown fences.\n"
    )


def correct_translation(
    source: dict[str, str],
    previous_translation: dict[str, str],
    lang_code: str,
    reviewer_comment: str,
    model: str = TRANSLATOR_MODEL,
) -> dict[str, str]:
    """Re-translate with reviewer feedback for one language.

    Args:
        source: Original Ukrainian field values.
        previous_translation: Previous translation that was below threshold.
        lang_code: Target language code.
        reviewer_comment: Feedback from the reviewer.
        model: Gemini model for correction (default: flash).

    Returns:
        Corrected field values for the language.

    """
    api_key: str = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    prompt = _build_correction_prompt(
        source,
        previous_translation,
        lang_code,
        reviewer_comment,
    )

    lang_name = _LANG_NAMES.get(lang_code, lang_code)
    logger.info("Correcting %s translation with %s", lang_name, model)

    response = client.models.generate_content(model=model, contents=prompt)

    meta = response.usage_metadata
    if meta:
        usage_stats.record(
            prompt_tokens=meta.prompt_token_count or 0,
            completion_tokens=meta.candidates_token_count or 0,
            model=model,
        )

    raw_text = response.text or ""
    try:
        result = _extract_flat_json(raw_text)
        return {k: str(v) for k, v in result.items()}
    except json.JSONDecodeError, ValueError:
        logger.error("Failed to parse correction response: %s", raw_text[:300])
        # Fall back to previous translation on parse failure.
        return previous_translation


# ---------------------------------------------------------------------------
# Two-role pipeline: translate → review → correct (per language)
# ---------------------------------------------------------------------------


@dataclass
class TranslationResult:
    """Result of the two-role translation pipeline for one language."""

    lang_code: str
    fields: dict[str, str]
    scores: ReviewScores
    iterations: int


def translate_and_review(
    source: dict[str, str],
    target_languages: list[str],
    field_kinds: dict[str, ContentKind] | None = None,
) -> dict[str, TranslationResult]:
    """Full two-role pipeline: translate all languages, then review each.

    1. Translate all languages in one API call (gemini-flash, cheap).
    2. Review each language individually (gemini-pro, accurate).
    3. If score < threshold, correct and re-review (max 2 iterations).

    Args:
        source: Ukrainian field values.
        target_languages: Language codes to translate into.
        field_kinds: Field content kinds (plain/html).

    Returns:
        Dict of lang_code -> TranslationResult with final fields and scores.

    """
    # Step 1: Initial translation (all languages, flash model).
    raw_translations = translate_with_gemini(
        source,
        target_languages,
        model=TRANSLATOR_MODEL,
        field_kinds=field_kinds,
    )

    results: dict[str, TranslationResult] = {}

    for lang in target_languages:
        lang_fields = raw_translations.get(lang, {})
        if not lang_fields:
            logger.warning("No translation for %s — skipping review", lang)
            results[lang] = TranslationResult(
                lang_code=lang,
                fields={},
                scores=ReviewScores(),
                iterations=0,
            )
            continue

        current_fields = lang_fields
        iteration = 0

        for iteration in range(1, MAX_CORRECTION_ITERATIONS + 2):
            # Step 2: Review.
            scores = review_translation(source, current_fields, lang)

            lang_name = _LANG_NAMES.get(lang, lang)
            logger.info(
                "Review %s (iter %d): avg=%.1f [acc=%.1f emo=%.1f "
                "qual=%.1f sty=%.1f gram=%.1f eth=%.1f]%s",
                lang_name,
                iteration,
                scores.average,
                scores.accuracy,
                scores.emotion,
                scores.quality,
                scores.style,
                scores.grammar,
                scores.ethics,
                "" if scores.passed else f" — NEEDS CORRECTION: {scores.comment}",
            )

            if scores.passed or iteration > MAX_CORRECTION_ITERATIONS:
                break

            # Step 3: Correct based on feedback.
            current_fields = correct_translation(
                source,
                current_fields,
                lang,
                scores.comment,
            )

        results[lang] = TranslationResult(
            lang_code=lang,
            fields=current_fields,
            scores=scores,
            iterations=iteration,
        )

    return results
