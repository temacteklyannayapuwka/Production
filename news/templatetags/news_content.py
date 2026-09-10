"""Template filters for safely prepared editorial content."""

from django import template
from django.utils.safestring import mark_safe

from news.content import clean_legacy_markup


register = template.Library()


@register.filter(is_safe=True)
def public_article_html(value):
    """Hide unsupported legacy editor syntax in already imported articles."""
    return mark_safe(clean_legacy_markup(value))
