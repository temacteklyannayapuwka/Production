"""Import structured Joomla K2 exports into the Stavplus news models."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.files import File
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags
from django.utils.text import slugify
from transliterate import translit

from news.models import Category, News, Tag


class K2ImportError(ValueError):
    """Raised when a legacy export cannot be imported safely."""


@dataclass(frozen=True)
class K2Dataset:
    categories: list[dict[str, Any]]
    tags: list[dict[str, Any]]
    tag_links: list[dict[str, Any]]
    items: list[dict[str, Any]]

    @classmethod
    def from_json(cls, path: Path) -> "K2Dataset":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise K2ImportError(f"Не удалось прочитать JSON: {error}") from error

        tables = cls._extract_tables(payload)
        missing = [
            name for name in ("categories", "items") if name not in tables
        ]
        if missing:
            raise K2ImportError(
                "В выгрузке отсутствуют обязательные таблицы K2: "
                + ", ".join(missing)
            )

        return cls(
            categories=cls._records(tables.get("categories", []), "categories"),
            tags=cls._records(tables.get("tags", []), "tags"),
            tag_links=cls._records(tables.get("tag_links", []), "tag_links"),
            items=cls._records(tables.get("items", []), "items"),
        )

    @staticmethod
    def _records(value: Any, name: str) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise K2ImportError(f"Таблица {name} должна быть массивом объектов.")
        return value

    @classmethod
    def _extract_tables(cls, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            if isinstance(payload.get("tables"), list):
                return cls._extract_phpmyadmin_tables(payload["tables"])
            aliases = {
                "categories": payload.get("categories", payload.get("k2_categories")),
                "tags": payload.get("tags", payload.get("k2_tags")),
                "tag_links": payload.get("tag_links", payload.get("k2_tags_xref")),
                "items": payload.get("items", payload.get("k2_items")),
            }
            return {name: rows for name, rows in aliases.items() if rows is not None}
        if isinstance(payload, list):
            return cls._extract_phpmyadmin_tables(payload)
        raise K2ImportError("Корень JSON должен быть объектом или массивом phpMyAdmin.")

    @staticmethod
    def _extract_phpmyadmin_tables(entries: list[Any]) -> dict[str, Any]:
        suffixes = {
            "_k2_categories": "categories",
            "_k2_tags_xref": "tag_links",
            "_k2_tags": "tags",
            "_k2_items": "items",
        }
        tables: dict[str, Any] = {}
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "table":
                continue
            table_name = str(entry.get("name", "")).lower()
            for suffix, target in suffixes.items():
                if table_name.endswith(suffix):
                    tables[target] = entry.get("data", [])
                    break
        return tables


class K2MediaIndex:
    """Resolve the K2 hash-based main image names without repeated directory scans."""

    def __init__(self, root: Path | None):
        self.root = root
        self.files: dict[str, Path] = {}
        if root is None:
            return
        for relative_directory in (Path("items/src"), Path("items/cache")):
            directory = root / relative_directory
            if not directory.is_dir():
                continue
            for path in directory.iterdir():
                if path.is_file():
                    self.files[path.name.lower()] = path

    def find_main_image(self, legacy_id: int) -> Path | None:
        digest = hashlib.md5(f"Image{legacy_id}".encode()).hexdigest()
        names = []
        for extension in ("jpg", "jpeg", "png", "webp"):
            names.append(f"{digest}.{extension}")
        for size in ("XL", "L", "Generic"):
            for extension in ("jpg", "jpeg", "png", "webp"):
                names.append(f"{digest}_{size}.{extension}")
        for name in names:
            if path := self.files.get(name.lower()):
                return path
        return None


class K2Importer:
    """Create or update Stavplus records from one structured K2 dataset."""

    def __init__(
        self,
        dataset: K2Dataset,
        *,
        media_root: Path | None,
        copy_images: bool,
        limit: int | None = None,
    ):
        self.dataset = dataset
        self.media = K2MediaIndex(media_root)
        self.copy_images = copy_images
        self.limit = limit
        self.stats: Counter[str] = Counter()
        self.written_files: list[tuple[Any, str]] = []

    def run(self) -> Counter[str]:
        categories = self._import_categories()
        tags = self._import_tags()
        tag_links = self._group_tag_links()
        self._import_news(categories, tags, tag_links)
        return self.stats

    def cleanup_written_files(self) -> None:
        for storage, name in reversed(self.written_files):
            try:
                if storage.exists(name):
                    storage.delete(name)
            except OSError:
                pass

    def _import_categories(self) -> dict[int, Category]:
        imported: dict[int, Category] = {}
        for position, row in enumerate(self.dataset.categories, start=1):
            legacy_id = self._required_id(row, "категории")
            raw_slug = row.get("alias") or row.get("slug") or row.get("name")
            category = Category.objects.filter(legacy_k2_id=legacy_id).first()
            if category is None:
                category = self._find_unclaimed_category(row, raw_slug)
            created = category is None
            if created:
                category = Category(legacy_k2_id=legacy_id)
            elif category.legacy_k2_id is None:
                category.legacy_k2_id = legacy_id

            category.name = str(row.get("name") or f"Категория K2 #{legacy_id}")[:100]
            category.slug = self._unique_slug(
                Category,
                raw_slug,
                fallback=f"k2-category-{legacy_id}",
                instance=category,
                max_length=100,
            )
            category.description = str(row.get("description") or "")
            category.order = self._as_int(row.get("ordering"), position)
            category.is_active = self._as_bool(row.get("published"), default=True)
            category.save()
            imported[legacy_id] = category
            self.stats["categories_created" if created else "categories_updated"] += 1
        return imported

    def _import_tags(self) -> dict[int, Tag]:
        imported: dict[int, Tag] = {}
        for row in self.dataset.tags:
            legacy_id = self._required_id(row, "тега")
            raw_slug = row.get("alias") or row.get("slug") or row.get("name")
            tag = Tag.objects.filter(legacy_k2_id=legacy_id).first()
            if tag is None:
                tag = self._find_unclaimed_tag(row, raw_slug)
            created = tag is None
            if created:
                tag = Tag(legacy_k2_id=legacy_id)
            elif tag.legacy_k2_id is None:
                tag.legacy_k2_id = legacy_id

            tag.name = str(row.get("name") or f"Тег K2 #{legacy_id}")[:80]
            tag.slug = self._unique_slug(
                Tag,
                raw_slug,
                fallback=f"k2-tag-{legacy_id}",
                instance=tag,
                max_length=100,
            )
            tag.description = str(row.get("description") or "")
            tag.is_active = self._as_bool(row.get("published"), default=True)
            tag.save()
            imported[legacy_id] = tag
            self.stats["tags_created" if created else "tags_updated"] += 1
        return imported

    def _import_news(
        self,
        categories: dict[int, Category],
        tags: dict[int, Tag],
        tag_links: dict[int, list[int]],
    ) -> None:
        rows = [row for row in self.dataset.items if not self._is_trashed(row)]
        if self.limit is not None:
            rows = rows[: self.limit]
        featured_id = self._featured_item_id(rows)

        for row in rows:
            legacy_id = self._required_id(row, "новости")
            news = News.objects.filter(legacy_k2_id=legacy_id).first()
            created = news is None
            if created:
                news = News(legacy_k2_id=legacy_id)

            title = str(row.get("title") or f"Материал K2 #{legacy_id}")[:255]
            raw_slug = row.get("alias") or row.get("slug") or title
            publication_time = self._parse_date(row.get("publish_up") or row.get("created"))
            publication_time = publication_time or timezone.now()
            expiration_time = self._parse_date(row.get("publish_down"))
            status = self._editorial_status(row, publication_time)
            intro = str(row.get("introtext") or "")
            full = str(row.get("fulltext") or "")
            content = f"{intro}{full}".strip() or "<p></p>"

            news.title = title
            news.slug = self._unique_slug(
                News,
                raw_slug,
                fallback=f"k2-news-{legacy_id}",
                instance=news,
                max_length=255,
            )
            category_id = self._as_int(row.get("catid"), 0)
            news.category = categories.get(category_id)
            if category_id and news.category is None:
                self.stats["missing_category_links"] += 1
            news.content = content
            news.excerpt = strip_tags(intro).strip()[:500]
            news.editorial_status = status
            news.is_featured = legacy_id == featured_id
            news.date_start = publication_time
            news.date_end = expiration_time
            news.views = max(0, self._as_int(row.get("hits"), 0))
            news.meta_title = str(row.get("metatitle") or title)[:255]
            news.meta_description = str(row.get("metadesc") or "")[:255]
            news.meta_keywords = str(row.get("metakey") or "")[:255]
            news.save()

            linked_tags = [tags[tag_id] for tag_id in tag_links.get(legacy_id, []) if tag_id in tags]
            news.tags.set(linked_tags)
            missing_tags = sum(tag_id not in tags for tag_id in tag_links.get(legacy_id, []))
            self.stats["missing_tag_links"] += missing_tags

            self._attach_main_image(news, legacy_id)
            self.stats["news_created" if created else "news_updated"] += 1

        self.stats["news_skipped_trash"] = len(self.dataset.items) - len(
            [row for row in self.dataset.items if not self._is_trashed(row)]
        )

    def _attach_main_image(self, news: News, legacy_id: int) -> None:
        if news.main_photo:
            self.stats["images_existing"] += 1
            return
        image_path = self.media.find_main_image(legacy_id)
        if image_path is None:
            self.stats["images_missing"] += 1
            return
        self.stats["images_found"] += 1
        if not self.copy_images:
            return
        target_name = f"k2-{legacy_id}{image_path.suffix.lower()}"
        with image_path.open("rb") as source:
            news.main_photo.save(target_name, File(source), save=True)
        self.written_files.append((news.main_photo.storage, news.main_photo.name))
        self.stats["images_copied"] += 1

    def _group_tag_links(self) -> dict[int, list[int]]:
        links: dict[int, list[int]] = defaultdict(list)
        for row in self.dataset.tag_links:
            item_id = self._as_int(row.get("itemID", row.get("item_id")), 0)
            tag_id = self._as_int(row.get("tagID", row.get("tag_id")), 0)
            if item_id and tag_id:
                links[item_id].append(tag_id)
        return links

    @classmethod
    def _featured_item_id(cls, rows: list[dict[str, Any]]) -> int | None:
        featured = [
            row
            for row in rows
            if cls._as_bool(row.get("featured"), default=False)
            and cls._editorial_status(
                row,
                cls._parse_date(row.get("publish_up") or row.get("created"))
                or timezone.now(),
            )
            == News.EditorialStatus.PUBLISHED
        ]
        if not featured:
            return None

        def timestamp(row: dict[str, Any]) -> float:
            value = cls._parse_date(row.get("publish_up") or row.get("created"))
            return value.timestamp() if value else 0

        return cls._as_int(max(featured, key=timestamp).get("id"), 0) or None

    @classmethod
    def _editorial_status(cls, row: dict[str, Any], publication_time: datetime) -> str:
        if not cls._as_bool(row.get("published"), default=False):
            return News.EditorialStatus.DRAFT
        if publication_time > timezone.now():
            return News.EditorialStatus.SCHEDULED
        return News.EditorialStatus.PUBLISHED

    @classmethod
    def _is_trashed(cls, row: dict[str, Any]) -> bool:
        return cls._as_bool(row.get("trash"), default=False) or cls._as_int(
            row.get("published"), 0
        ) == -2

    @staticmethod
    def _find_unclaimed_category(row: dict[str, Any], raw_slug: Any) -> Category | None:
        slug = slugify(str(raw_slug or ""))
        query = models.Q(name=str(row.get("name") or ""))
        if slug:
            query |= models.Q(slug=slug)
        return Category.objects.filter(query, legacy_k2_id__isnull=True).first()

    @staticmethod
    def _find_unclaimed_tag(row: dict[str, Any], raw_slug: Any) -> Tag | None:
        slug = slugify(str(raw_slug or ""))
        query = models.Q(name=str(row.get("name") or ""))
        if slug:
            query |= models.Q(slug=slug)
        return Tag.objects.filter(query, legacy_k2_id__isnull=True).first()

    @classmethod
    def _unique_slug(
        cls,
        model: type[models.Model],
        raw_value: Any,
        *,
        fallback: str,
        instance: models.Model,
        max_length: int,
    ) -> str:
        value = str(raw_value or "").strip()
        try:
            value = translit(value, "ru", reversed=True)
        except Exception:
            pass
        base = slugify(value)[:max_length] or fallback
        candidate = base
        suffix = 2
        while model.objects.exclude(pk=instance.pk).filter(slug=candidate).exists():
            marker = f"-{suffix}"
            candidate = f"{base[: max_length - len(marker)]}{marker}"
            suffix += 1
        return candidate

    @classmethod
    def _required_id(cls, row: dict[str, Any], label: str) -> int:
        legacy_id = cls._as_int(row.get("id"), 0)
        if legacy_id <= 0:
            raise K2ImportError(f"У {label} отсутствует корректный положительный id: {row!r}")
        return legacy_id

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_bool(value: Any, *, default: bool) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw or raw.startswith("0000-00-00"):
            return None
        parsed = parse_datetime(raw)
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError as error:
                raise K2ImportError(f"Некорректная дата K2: {raw}") from error
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
        return parsed
