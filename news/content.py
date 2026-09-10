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
    return cleaned.replace("&amp;nbsp;", " ").replace("&nbsp;", " ")
