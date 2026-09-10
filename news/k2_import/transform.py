from __future__ import annotations

from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from transliterate import translit

from news.models import News

from .domain import LegacyItem, PublicationValues


ZERO_DATES = {"", "0000-00-00", "0000-00-00 00:00:00"}


def parse_legacy_datetime(value, legacy_timezone: ZoneInfo) -> datetime | None:
    """Interpret a K2 wall-clock value in the explicitly configured Joomla timezone."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text in ZERO_DATES:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"invalid legacy datetime {text!r}") from error

    if timezone.is_naive(parsed):
        return parsed.replace(tzinfo=legacy_timezone)
    return parsed.astimezone(legacy_timezone)


def publication_values(
    item: LegacyItem,
    *,
    legacy_timezone: ZoneInfo,
    now: datetime,
) -> PublicationValues:
    created = parse_legacy_datetime(item.created, legacy_timezone)
    publish_up = parse_legacy_datetime(item.publish_up, legacy_timezone)
    publish_down = parse_legacy_datetime(item.publish_down, legacy_timezone)
    date_start = publish_up or created or now

    if int(item.published) != 1:
        status = News.EditorialStatus.DRAFT
        is_published = False
    elif date_start > now:
        status = News.EditorialStatus.SCHEDULED
        is_published = True
    else:
        status = News.EditorialStatus.PUBLISHED
        is_published = True

    return PublicationValues(
        editorial_status=status,
        is_published=is_published,
        date_start=date_start,
        date_end=publish_down,
    )


def clean_excerpt(value: str, max_length: int = 500) -> str:
    text = " ".join(unescape(strip_tags(value or "")).split())
    return text[:max_length]


def split_legacy_content(introtext: str, fulltext: str) -> tuple[str, str]:
    """Map K2's lead/body fields without rendering the lead twice.

    K2 renders ``introtext`` before ``fulltext``. StavPlus stores that lead in
    ``excerpt`` and renders it separately, so only ``fulltext`` belongs in the
    article body. Items without a separate body keep their intro as content and
    leave the excerpt empty, which still renders the text exactly once.
    """
    intro = (introtext or "").strip()
    body = (fulltext or "").strip()
    if body:
        return body, clean_excerpt(intro)
    return intro, ""


def slug_base(value: str, fallback: str) -> str:
    candidate = slugify(value or "")
    if not candidate and value:
        try:
            candidate = slugify(translit(value, "ru", reversed=True))
        except Exception:
            candidate = ""
    return candidate or fallback


class SlugAllocator:
    """Allocate deterministic slugs against both the database and the current run."""

    def __init__(self, model, max_length: int):
        self.model = model
        self.max_length = max_length
        self.reserved = set(model.objects.values_list("slug", flat=True))

    def allocate(self, desired: str, legacy_id: int) -> tuple[str, bool]:
        base = slug_base(desired, f"k2-{legacy_id}")[: self.max_length].rstrip("-")
        if base not in self.reserved:
            self.reserved.add(base)
            return base, False

        suffix = f"-k2-{legacy_id}"
        candidate = f"{base[: self.max_length - len(suffix)].rstrip('-')}{suffix}"
        counter = 2
        while candidate in self.reserved:
            numbered_suffix = f"{suffix}-{counter}"
            candidate = (
                f"{base[: self.max_length - len(numbered_suffix)].rstrip('-')}"
                f"{numbered_suffix}"
            )
            counter += 1
        self.reserved.add(candidate)
        return candidate, True
