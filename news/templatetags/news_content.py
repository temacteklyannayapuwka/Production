"""Template filters for safely prepared editorial content."""

import html
import re

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from news.content import clean_legacy_markup


register = template.Library()


@register.filter(is_safe=True)
def public_article_html(value):
    """Hide unsupported legacy editor syntax in already imported articles."""
    return mark_safe(clean_legacy_markup(value))


@register.filter
def public_plain_text(value):
    """Turn legacy editor HTML into compact, safely escaped plain text."""
    text = html.unescape(strip_tags(clean_legacy_markup(value)))
    return re.sub(r"\s+", " ", text).strip()
