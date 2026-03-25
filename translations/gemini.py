"""Google Gemini API client for menu content translation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

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

# Pricing per 1M tokens (USD) — gemini-2.5-flash as of 2026-03.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}

DEFAULT_MODEL = "gemini-2.5-flash"


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
        "You are a professional translator for a restaurant menu.\n"
        f"Translate the following content from Ukrainian to: {lang_list}.\n\n"
        f"Source (Ukrainian):\n{source_json}\n\n"
        "Rules:\n"
        "- Keep translations natural, appetizing, and culturally appropriate.\n"
        "- Preserve the original meaning and culinary terminology.\n"
        f"{cnr_rules}"
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
    model: str = DEFAULT_MODEL,
) -> dict[str, dict[str, str]]:
    """Translate source fields to all target languages in one API call.

    Args:
        source: Field names to Ukrainian text, e.g. {"title": "Борщ", "description": "..."}.
        target_languages: Language codes, e.g. ["en", "cnr", "hr", "bs", "it", "de"].
        model: Gemini model to use.

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
        "Calling Gemini (%s) for %d fields -> %d languages",
        model,
        len(source),
        len(target_languages),
    )

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

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
        result = _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Gemini response: %s", raw_text[:500])
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc

    # Validate structure: ensure all requested languages are present.
    missing = set(target_languages) - set(result.keys())
    if missing:
        logger.warning("Gemini response missing languages: %s", missing)

    return result
