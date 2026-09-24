"""Safe template helpers for SEO metadata and image dimensions."""

import json

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = template.Library()

JSON_SCRIPT_ESCAPES = {
    ord(">"): "\\u003E",
    ord("<"): "\\u003C",
    ord("&"): "\\u0026",
    ord("\u2028"): "\\u2028",
    ord("\u2029"): "\\u2029",
}


@register.simple_tag
def json_ld(value):
    """Serialize JSON-LD without allowing data to terminate the script tag."""
    if not value:
        return ""
    encoded = json.dumps(
        value,
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
    ).translate(JSON_SCRIPT_ESCAPES)
    return format_html(
        '<script type="application/ld+json">{}</script>',
        mark_safe(encoded),
    )


@register.simple_tag
def image_dimensions(image):
    """Return intrinsic dimensions when storage can inspect the image safely."""
    if not image:
        return ""
    try:
        width = int(image.width)
        height = int(image.height)
    except (AttributeError, FileNotFoundError, OSError, TypeError, ValueError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    return format_html('width="{}" height="{}"', width, height)
