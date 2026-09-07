from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from news.models import Category, News, Tag

from .domain import ImportReport, LegacyCategory, LegacyItem, LegacyTag
from .media import K2AssetMigrator
from .transform import SlugAllocator, clean_excerpt, combine_content, publication_values


class K2Importer:
    """Synchronize one Joomla K2 source into StavPlus with per-record recovery."""

    def __init__(
        self,
        source,
        *,
        legacy_root: Path,
        legacy_timezone: ZoneInfo,
        apply: bool = False,
        now: datetime | None = None,
        storage=None,
    ):
        self.source = source
        self.apply = apply
        self.legacy_timezone = legacy_timezone
        self.now = now or timezone.now()
        self.report = ImportReport(dry_run=not apply)
        asset_kwargs = {"apply": apply}
        if storage is not None:
            asset_kwargs["storage"] = storage
        self.assets = K2AssetMigrator(legacy_root, self.report, **asset_kwargs)

    def run(
        self,
        *,
        limit: int | None = None,
        resume_from_id: int | None = None,
        exclude_category_ids: set[int] | None = None,
    ) -> ImportReport:
        excluded = exclude_category_ids or set()
        categories = self.source.fetch_categories()
        tags = self.source.fetch_tags()
        tag_links = self.source.fetch_tag_links()
        self.report.counts.update(
            {
                "categories_found": len(categories),
                "tags_found": len(tags),
            }
        )

        category_map = self._sync_categories(categories)
        tag_map = self._sync_tags(tags)
        category_ids = {category.legacy_id for category in categories}
        tag_ids = {tag.legacy_id for tag in tags}
        tag_ids_by_item: dict[int, list[int]] = defaultdict(list)
        for item_id, tag_id in tag_links:
            tag_ids_by_item[item_id].append(tag_id)

        news_slug_allocator = SlugAllocator(News, 255)
        featured_candidates: list[tuple[datetime, int, int | None]] = []
        items = self.source.iter_items(
            limit=limit,
            resume_from_id=resume_from_id,
            exclude_category_ids=excluded,
        )
        for item in items:
            self.report.increment("news_found")
            if item.trashed or int(item.published) < 0 or item.category_id in excluded:
                self.report.increment("news_skipped")
                continue
            try:
                result = self._sync_item(
                    item,
                    category_ids=category_ids,
                    category_map=category_map,
                    tag_ids=tag_ids,
                    tag_map=tag_map,
                    item_tag_ids=tag_ids_by_item.get(item.legacy_id, []),
                    slug_allocator=news_slug_allocator,
                )
            except Exception as error:
                self.report.error("news", item.legacy_id, error)
                self.report.increment("news_skipped")
                continue

            if result is None:
                continue
            publication, news_pk = result
            if item.featured:
                self.report.increment("featured_found")
                active_end = publication.date_end is None or publication.date_end >= self.now
                if publication.editorial_status == News.EditorialStatus.PUBLISHED and active_end:
                    featured_candidates.append(
                        (publication.date_start, item.legacy_id, news_pk)
                    )

        self._select_featured(featured_candidates)
        self.report.finish()
        return self.report

    def _sync_categories(self, categories: list[LegacyCategory]) -> dict[int, Category]:
        mapped: dict[int, Category] = {}
        name_owners: dict[str, int] = {}
        allocator = SlugAllocator(Category, 100)
        for record in categories:
            try:
                name = self._bounded_text(
                    record.name,
                    100,
                    entity="category",
                    legacy_id=record.legacy_id,
                    field="name",
                )
                if not name:
                    raise ValueError("category name is empty")
                owner_id = name_owners.get(name)
                if owner_id is not None:
                    self._merge_duplicate_name(
                        "category",
                        record.legacy_id,
                        name,
                        owner_id,
                    )
                    if self.apply and owner_id in mapped:
                        mapped[record.legacy_id] = mapped[owner_id]
                    continue
                name_owners[name] = record.legacy_id

                obj = Category.objects.filter(legacy_k2_id=record.legacy_id).first()
                if obj is None:
                    obj = Category.objects.filter(name=name).first()
                    if obj is not None and obj.legacy_k2_id is not None:
                        self._merge_duplicate_name(
                            "category",
                            record.legacy_id,
                            name,
                            obj.legacy_k2_id,
                        )
                        if self.apply:
                            mapped[record.legacy_id] = obj
                        continue
                creating = obj is None
                if creating:
                    slug, collided = allocator.allocate(record.alias or name, record.legacy_id)
                    if collided:
                        self._slug_collision("category", record.legacy_id, record.alias or name, slug)
                else:
                    slug = obj.slug

                if not self.apply:
                    self.report.increment(
                        "categories_would_create" if creating else "categories_would_update"
                    )
                    if obj is not None:
                        mapped[record.legacy_id] = obj
                    continue

                values = {
                    "legacy_k2_id": record.legacy_id,
                    "name": name,
                    "slug": slug,
                    "description": record.description,
                    "order": record.ordering,
                    "is_active": record.published,
                }
                with transaction.atomic():
                    if creating:
                        obj = Category.objects.create(**values)
                        self.report.increment("categories_created")
                    else:
                        Category.objects.filter(pk=obj.pk).update(**values)
                        obj.refresh_from_db()
                        self.report.increment("categories_updated")
                mapped[record.legacy_id] = obj
            except Exception as error:
                self.report.error("category", record.legacy_id, error)
        return mapped

    def _sync_tags(self, tags: list[LegacyTag]) -> dict[int, Tag]:
        mapped: dict[int, Tag] = {}
        name_owners: dict[str, int] = {}
        allocator = SlugAllocator(Tag, 100)
        for record in tags:
            try:
                name = self._bounded_text(
                    record.name,
                    80,
                    entity="tag",
                    legacy_id=record.legacy_id,
                    field="name",
                )
                if not name:
                    raise ValueError("tag name is empty")
                owner_id = name_owners.get(name)
                if owner_id is not None:
                    self._merge_duplicate_name(
                        "tag",
                        record.legacy_id,
                        name,
                        owner_id,
                    )
                    if self.apply and owner_id in mapped:
                        mapped[record.legacy_id] = mapped[owner_id]
                    continue
                name_owners[name] = record.legacy_id

                obj = Tag.objects.filter(legacy_k2_id=record.legacy_id).first()
                if obj is None:
                    obj = Tag.objects.filter(name=name).first()
                    if obj is not None and obj.legacy_k2_id is not None:
                        self._merge_duplicate_name(
                            "tag",
                            record.legacy_id,
                            name,
                            obj.legacy_k2_id,
                        )
                        if self.apply:
                            mapped[record.legacy_id] = obj
                        continue
                creating = obj is None
                if creating:
                    slug, collided = allocator.allocate(record.alias or name, record.legacy_id)
                    if collided:
                        self._slug_collision("tag", record.legacy_id, record.alias or name, slug)
                else:
                    slug = obj.slug

                if not self.apply:
                    self.report.increment("tags_would_create" if creating else "tags_would_update")
                    if obj is not None:
                        mapped[record.legacy_id] = obj
                    continue

                values = {
                    "legacy_k2_id": record.legacy_id,
                    "name": name,
                    "slug": slug,
                    "is_active": record.published,
                }
                with transaction.atomic():
                    if creating:
                        obj = Tag.objects.create(**values)
                        self.report.increment("tags_created")
                    else:
                        Tag.objects.filter(pk=obj.pk).update(**values)
                        obj.refresh_from_db()
                        self.report.increment("tags_updated")
                mapped[record.legacy_id] = obj
            except Exception as error:
                self.report.error("tag", record.legacy_id, error)
        return mapped

    def _merge_duplicate_name(
        self,
        entity: str,
        legacy_id: int,
        name: str,
        owner_id: int,
    ) -> None:
        self.report.issue(
            f"duplicate_{entity}_names",
            f"name {name!r} duplicates legacy {entity} {owner_id}; "
            "both records use one target object",
            entity=entity,
            legacy_id=legacy_id,
        )
        merged_count = "categories_merged" if entity == "category" else "tags_merged"
        self.report.increment(merged_count)

    def _sync_item(
        self,
        item: LegacyItem,
        *,
        category_ids: set[int],
        category_map: dict[int, Category],
        tag_ids: set[int],
        tag_map: dict[int, Tag],
        item_tag_ids: list[int],
        slug_allocator: SlugAllocator,
    ):
        title = self._bounded_text(
            item.title,
            255,
            entity="news",
            legacy_id=item.legacy_id,
            field="title",
        )
        if not title:
            raise ValueError("news title is empty")
        publication = publication_values(
            item,
            legacy_timezone=self.legacy_timezone,
            now=self.now,
        )
        self.report.increment(f"news_{publication.editorial_status}")
        if publication.date_end and publication.date_end < publication.date_start:
            self.report.issue(
                "date_problems",
                "publish_down is earlier than date_start",
                entity="news",
                legacy_id=item.legacy_id,
            )

        if item.category_id is not None and item.category_id not in category_ids:
            self.report.issue(
                "missing_category_references",
                f"category {item.category_id} was not found",
                entity="news",
                legacy_id=item.legacy_id,
            )
        elif (
            self.apply
            and item.category_id is not None
            and item.category_id not in category_map
        ):
            self.report.issue(
                "unmapped_category_references",
                f"category {item.category_id} could not be synchronized",
                entity="news",
                legacy_id=item.legacy_id,
            )
        category = category_map.get(item.category_id) if self.apply else None

        missing_tag_ids = sorted(set(item_tag_ids) - tag_ids)
        for missing_tag_id in missing_tag_ids:
            self.report.issue(
                "missing_tag_references",
                f"tag {missing_tag_id} was not found",
                entity="news",
                legacy_id=item.legacy_id,
            )
        for unmapped_tag_id in sorted(
            tag_id
            for tag_id in item_tag_ids
            if self.apply and tag_id in tag_ids and tag_id not in tag_map
        ):
            self.report.issue(
                "unmapped_tag_references",
                f"tag {unmapped_tag_id} could not be synchronized",
                entity="news",
                legacy_id=item.legacy_id,
            )
        mapped_tags = [tag_map[tag_id] for tag_id in item_tag_ids if tag_id in tag_map]

        raw_content = combine_content(item.introtext, item.fulltext)
        content = self.assets.rewrite_html(raw_content, entity_id=item.legacy_id)
        main_image = self.assets.main_image_name(item.legacy_id)
        existing = News.objects.filter(legacy_k2_id=item.legacy_id).first()
        creating = existing is None
        if creating:
            slug, collided = slug_allocator.allocate(item.alias or title, item.legacy_id)
            if collided:
                self._slug_collision("news", item.legacy_id, item.alias or title, slug)
        else:
            slug = existing.slug

        payload = {
            "legacy_k2_id": item.legacy_id,
            "title": title,
            "content": content,
            "excerpt": clean_excerpt(item.introtext),
            "category": category,
            "is_published": publication.is_published,
            "editorial_status": publication.editorial_status,
            "is_featured": False,
            "date_start": publication.date_start,
            "date_end": publication.date_end,
            "meta_title": title,
            "meta_description": self._bounded_text(
                item.meta_description,
                255,
                entity="news",
                legacy_id=item.legacy_id,
                field="meta_description",
            ),
            "meta_keywords": self._bounded_text(
                item.meta_keywords,
                255,
                entity="news",
                legacy_id=item.legacy_id,
                field="meta_keywords",
            ),
            "views": max(0, int(item.hits or 0)),
        }
        if main_image is not None or creating:
            payload["main_photo"] = main_image or ""

        if not self.apply:
            self.report.increment("news_would_create" if creating else "news_would_update")
            return publication, existing.pk if existing is not None else None

        with transaction.atomic():
            if creating:
                news = News(slug=slug, **payload)
                News.objects.bulk_create([news])
                self.report.increment("news_imported")
            else:
                News.objects.filter(pk=existing.pk).update(**payload)
                existing.refresh_from_db()
                news = existing
                self.report.increment("news_updated")
            news.tags.set(mapped_tags)
        self.report.last_successful_legacy_id = item.legacy_id
        return publication, news.pk

    def _select_featured(self, candidates: list[tuple[datetime, int, int | None]]) -> None:
        if not candidates:
            return
        _, legacy_id, news_pk = max(candidates, key=lambda item: (item[0], item[1]))
        self.report.selected_featured_legacy_id = legacy_id
        if self.apply and news_pk is not None:
            with transaction.atomic():
                News.objects.filter(is_featured=True).update(is_featured=False)
                News.objects.filter(pk=news_pk).update(is_featured=True)
            self.report.increment("featured_selected")

    def _bounded_text(
        self,
        value: str,
        max_length: int,
        *,
        entity: str,
        legacy_id: int,
        field: str,
    ) -> str:
        text = str(value or "")
        if len(text) > max_length:
            self.report.issue(
                "truncated_fields",
                f"{field} exceeded {max_length} characters",
                entity=entity,
                legacy_id=legacy_id,
            )
        return text[:max_length]

    def _slug_collision(self, entity: str, legacy_id: int, desired: str, result: str) -> None:
        self.report.issue(
            "slug_collisions",
            f"{desired!r} resolved as {result!r}",
            entity=entity,
            legacy_id=legacy_id,
        )
