"""Template helpers for readable search-result highlights."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter(is_safe=True)
def highlight_query(value, query):
    """Escape text and wrap every case-insensitive query match in ``mark``."""
    text = str(value or '')
    needle = str(query or '').strip()
    if not needle:
        return escape(text)

    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    fragments = []
    cursor = 0
    for match in pattern.finditer(text):
        fragments.append(escape(text[cursor:match.start()]))
        fragments.append(format_html('<mark class="search-highlight">{}</mark>', match.group(0)))
        cursor = match.end()
    fragments.append(escape(text[cursor:]))
    return mark_safe(''.join(fragments))
