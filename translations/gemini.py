"""Google Gemini API client for menu content translation."""

from __future__ import annotations

import json
import logging
import re

from django.conf import settings
from google import genai

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


def _build_prompt(source: dict[str, str], target_languages: list[str]) -> str:
    """Build translation prompt for Gemini."""
    lang_list = ", ".join(
        f"{code} ({_LANG_NAMES.get(code, code)})" for code in target_languages
    )
    source_json = json.dumps(source, ensure_ascii=False, indent=2)

    return (
        "You are a professional translator for a restaurant menu.\n"
        f"Translate the following content from Ukrainian to: {lang_list}.\n\n"
        f"Source (Ukrainian):\n{source_json}\n\n"
        "Rules:\n"
        "- Keep translations natural, appetizing, and culturally appropriate.\n"
        "- Preserve the original meaning and culinary terminology.\n"
        "- For Montenegrin (cnr): use Latin script with specific letters (ś, ź).\n"
        "- Return ONLY valid JSON — no markdown fences, no explanation.\n\n"
        "Expected JSON format:\n"
        '{"en": {"title": "...", "description": "..."}, '
        '"cnr": {"title": "...", "description": "..."}, ...}\n\n'
        "Include all requested languages. Field keys must match the source exactly."
    )


def _extract_json(text: str) -> dict[str, dict[str, str]]:
    """Extract JSON from Gemini response, handling markdown fences."""
    # Strip markdown code fences if present.
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    return json.loads(cleaned)  # type: ignore[no-any-return]


def translate_with_gemini(
    source: dict[str, str],
    target_languages: list[str],
) -> dict[str, dict[str, str]]:
    """Translate source fields to all target languages in one API call.

    Args:
        source: Field names to Ukrainian text, e.g. {"title": "Борщ", "description": "..."}.
        target_languages: Language codes, e.g. ["en", "cnr", "hr", "bs", "it", "de"].

    Returns:
        Nested dict: {lang_code: {field_name: translated_text}}.

    Raises:
        ValueError: If API key is missing or response cannot be parsed.
        google.genai.errors.APIError: On Gemini API failures.

    """
    api_key: str = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(source, target_languages)
    logger.info(
        "Calling Gemini for %d fields -> %d languages",
        len(source),
        len(target_languages),
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw_text = response.text or ""
    logger.debug("Gemini raw response: %s", raw_text[:500])

    try:
        result = _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Gemini response: %s", raw_text[:500])
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc

    # Validate structure: ensure all requested languages are present.
    missing = set(target_languages) - set(result.keys())
    if missing:
        logger.warning("Gemini response missing languages: %s", missing)

    return result
