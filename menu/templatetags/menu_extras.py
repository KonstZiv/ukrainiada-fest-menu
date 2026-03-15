# ---------------------------------------------------------------------------
# menu_extras.py — Кастомні шаблонні фільтри для застосунку menu (таска 3.1)
#
# Django дозволяє створювати власні template tags та filters.
# Файл повинен знаходитися в <app>/templatetags/<module>.py.
# Підключається в шаблоні через {% load menu_extras %}.
#
# highlight — фільтр для підсвічування пошукових збігів:
#   {{ dish.title|highlight:query }} → обгортає збіги в <mark>...</mark>
#
# Документація:
#   https://docs.djangoproject.com/en/stable/howto/custom-template-tags/
#   https://docs.djangoproject.com/en/stable/howto/custom-template-tags/#writing-custom-template-filters
# ---------------------------------------------------------------------------

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

register = template.Library()


@register.filter(name="highlight")
def highlight(text: str, query: str) -> SafeString:
    """Wrap search query matches in <mark> tags for visual highlighting.

    Case-insensitive replacement using ``re.sub`` with ``re.IGNORECASE``.
    HTML-escapes the text first to prevent XSS, then wraps matches
    in ``<mark>`` tags and marks the result as safe.

    Args:
        text: The text to search within (e.g. dish title or description).
        query: The search query string to highlight.

    Returns:
        SafeString with matches wrapped in ``<mark>`` tags.

    Examples:
        >>> highlight("Борщ український", "борщ")
        '<mark>Борщ</mark> український'
        >>> highlight("Caesar Salad", "")
        'Caesar Salad'

    Documentation:
        https://docs.djangoproject.com/en/stable/howto/custom-template-tags/#writing-custom-template-filters

    """
    if not query or not text:
        return mark_safe(escape(str(text)))

    # --- Безпека: спершу екрануємо HTML --- #
    # escape() перетворює <, >, &, ", ' у HTML-entities.
    # Це запобігає XSS: якщо text містить <script>, він стане &lt;script&gt;.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.html.escape
    escaped_text = escape(str(text))
    escaped_query = escape(str(query))

    # --- re.sub з IGNORECASE для підсвічування збігів --- #
    # re.escape(query) — екранує спеціальні символи regex (., *, + тощо).
    # re.IGNORECASE — регістронезалежний пошук.
    # r"<mark>\g<0></mark>" — \g<0> це весь збіг (зберігає оригінальний регістр).
    # Документація:
    #   https://docs.python.org/3/library/re.html#re.sub
    pattern = re.compile(re.escape(escaped_query), re.IGNORECASE)
    result = pattern.sub(r"<mark>\g<0></mark>", escaped_text)

    # --- mark_safe: позначаємо результат як безпечний HTML --- #
    # Без mark_safe Django автоматично екранує HTML у шаблоні,
    # і <mark> стане видимим текстом замість HTML-тега.
    # Ми впевнені що результат безпечний, бо:
    #   1. text пройшов через escape() — XSS неможливий
    #   2. Додаємо лише <mark> теги — безпечний HTML
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.safestring.mark_safe
    return mark_safe(result)  # noqa: S308
