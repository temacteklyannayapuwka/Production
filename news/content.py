"""Public-facing cleanup for artifacts left by the legacy Joomla editor."""

from __future__ import annotations

import re


LEGACY_LIGHTBOX_RE = re.compile(
    r"\[\s*/?\s*lightbox\b(?:[^\]\"']+|\"[^\"]*\"|'[^']*')*\]",
    re.IGNORECASE,
)


def clean_legacy_markup(value: str) -> str:
    """Remove unsupported Joomla shortcodes without altering normal article HTML."""
    cleaned = LEGACY_LIGHTBOX_RE.sub("", str(value or ""))
    cleaned = cleaned.replace("&amp;nbsp;", " ").replace("&nbsp;", " ")
    # The page title is the single semantic H1. Editorial and legacy body
    # headings start at H2 even if stored content contains an H1 element.
    cleaned = re.sub(r"<h1(?=\s|>)", "<h2", cleaned, flags=re.IGNORECASE)
    return re.sub(r"</h1\s*>", "</h2>", cleaned, flags=re.IGNORECASE)
