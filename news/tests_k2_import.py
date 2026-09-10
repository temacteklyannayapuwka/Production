from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from news.k2_import import media as k2_media
from news.k2_import.domain import ImportReport, LegacyCategory, LegacyItem, LegacyTag
from news.k2_import.media import K2AssetMigrator, find_k2_main_image, k2_image_hash
from news.k2_import.service import K2Importer
from news.k2_import.transform import (
    parse_legacy_datetime,
    publication_values,
    split_legacy_content,
)
from news.models import Category, News, Tag


MOSCOW = ZoneInfo("Europe/Moscow")


class FakeK2Source:
    def __init__(self, *, categories=(), tags=(), tag_links=(), items=()):
        self.categories = list(categories)
        self.tags = list(tags)
        self.tag_links = list(tag_links)
        self.items = list(items)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def fetch_categories(self):
        return self.categories

    def fetch_tags(self):
        return self.tags

    def fetch_tag_links(self):
        return self.tag_links

    def iter_items(self, *, limit=None, resume_from_id=None, exclude_category_ids=None):
        excluded = exclude_category_ids or set()
        rows = [
            item
            for item in self.items
            if (resume_from_id is None or item.legacy_id >= resume_from_id)
            and item.category_id not in excluded
        ]
        yield from rows[:limit]


class K2TransformTests(TestCase):
    def test_k2_image_hash_and_preferred_image_order(self):
        self.assertEqual(k2_image_hash(42), "19f9cefdfb07230a68581d617885a3af")
        with TemporaryDirectory() as root:
            legacy_root = Path(root)
            cache = legacy_root / "media" / "k2" / "items" / "cache"
            source = legacy_root / "media" / "k2" / "items" / "src"
            cache.mkdir(parents=True)
            source.mkdir(parents=True)
            image_hash = k2_image_hash(42)
            (cache / f"{image_hash}_L.png").write_bytes(b"large")
            (cache / f"{image_hash}_XL.jpg").write_bytes(b"extra-large")

            self.assertEqual(find_k2_main_image(legacy_root, 42).suffix, ".jpg")
            original = source / f"{image_hash}.webp"
            original.write_bytes(b"original")
            self.assertEqual(find_k2_main_image(legacy_root, 42), original)

    def test_publication_status_mapping(self):
        now = datetime(2026, 9, 5, 12, tzinfo=MOSCOW)
        published = publication_values(
            LegacyItem(
                legacy_id=1,
                title="Published",
                published=1,
                publish_up="2026-09-05 10:00:00",
            ),
            legacy_timezone=MOSCOW,
            now=now,
        )
        scheduled = publication_values(
            LegacyItem(
                legacy_id=2,
                title="Scheduled",
                published=1,
                publish_up="2026-09-06 10:00:00",
            ),
            legacy_timezone=MOSCOW,
            now=now,
        )
        draft = publication_values(
            LegacyItem(
                legacy_id=3,
                title="Draft",
                published=0,
                publish_up="2026-09-05 10:00:00",
            ),
            legacy_timezone=MOSCOW,
            now=now,
        )

        self.assertEqual(published.editorial_status, News.EditorialStatus.PUBLISHED)
        self.assertEqual(scheduled.editorial_status, News.EditorialStatus.SCHEDULED)
        self.assertEqual(draft.editorial_status, News.EditorialStatus.DRAFT)
        self.assertFalse(draft.is_published)

    def test_legacy_datetime_uses_configured_timezone_and_handles_zero_date(self):
        parsed = parse_legacy_datetime("2026-01-15 10:30:00", MOSCOW)

        self.assertEqual(parsed.hour, 10)
        self.assertEqual(parsed.utcoffset(), timedelta(hours=3))
        self.assertIsNone(parse_legacy_datetime("0000-00-00 00:00:00", MOSCOW))

    def test_k2_intro_and_body_are_not_duplicated(self):
        content, excerpt = split_legacy_content(
            "<p>Короткий <b>анонс</b></p>",
            "<p>Основной текст</p>",
        )

        self.assertEqual(content, "<p>Основной текст</p>")
        self.assertEqual(excerpt, "Короткий анонс")

    def test_intro_only_item_is_rendered_once_as_content(self):
        content, excerpt = split_legacy_content("<p>Весь материал</p>", "")

        self.assertEqual(content, "<p>Весь материал</p>")
        self.assertEqual(excerpt, "")


class K2ImporterTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.category = LegacyCategory(legacy_id=10, name="Общество", alias="society")
        self.tag = LegacyTag(legacy_id=20, name="Ставрополь", alias="stavropol")

    def item(self, legacy_id=1, **overrides):
        values = {
            "title": f"Новость {legacy_id}",
            "alias": f"news-{legacy_id}",
            "category_id": self.category.legacy_id,
            "published": 1,
            "introtext": "<p>Короткий анонс</p>",
            "fulltext": "<p>Полный текст</p>",
            "created": self.now - timedelta(days=2),
            "publish_up": self.now - timedelta(days=1),
            "hits": 15,
        }
        values.update(overrides)
        return LegacyItem(legacy_id=legacy_id, **values)

    def source(self, *, items, tag_links=()):
        return FakeK2Source(
            categories=[self.category],
            tags=[self.tag],
            tag_links=tag_links,
            items=items,
        )

    def run_import(self, source, *, legacy_root, apply=True):
        return K2Importer(
            source,
            legacy_root=Path(legacy_root),
            legacy_timezone=MOSCOW,
            apply=apply,
            now=self.now,
        ).run()

    def test_apply_maps_category_tags_and_main_image(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            legacy_root = Path(root)
            image_dir = legacy_root / "media" / "k2" / "items" / "src"
            image_dir.mkdir(parents=True)
            (image_dir / f"{k2_image_hash(1)}.jpg").write_bytes(b"legacy-image")
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(
                    self.source(items=[self.item()], tag_links=[(1, 20)]),
                    legacy_root=legacy_root,
                )

            news = News.objects.get(legacy_k2_id=1)
            self.assertEqual(news.category.legacy_k2_id, 10)
            self.assertEqual(list(news.tags.values_list("legacy_k2_id", flat=True)), [20])
            self.assertTrue(news.main_photo.name.startswith("legacy/k2/items/1/"))
            self.assertEqual(report.counts["main_images_copied"], 1)

    def test_slug_collision_is_resolved_deterministically(self):
        News.objects.create(
            title="Existing",
            slug="same",
            content="Text",
            editorial_status=News.EditorialStatus.PUBLISHED,
        )
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(
                    self.source(items=[self.item(alias="same")]),
                    legacy_root=root,
                )

        self.assertEqual(News.objects.get(legacy_k2_id=1).slug, "same-k2-1")
        self.assertEqual(report.counts["slug_collisions"], 1)

    def test_second_import_updates_news_without_creating_duplicates(self):
        source = self.source(items=[self.item(title="Первая версия")], tag_links=[(1, 20)])
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                first_report = self.run_import(source, legacy_root=root)
                source.items = [self.item(title="Обновлённая версия")]
                second_report = self.run_import(source, legacy_root=root)

        self.assertEqual(News.objects.filter(legacy_k2_id=1).count(), 1)
        self.assertEqual(News.objects.get(legacy_k2_id=1).title, "Обновлённая версия")
        self.assertEqual(first_report.counts["news_imported"], 1)
        self.assertEqual(second_report.counts["news_updated"], 1)

    def test_existing_category_and_tag_are_adopted_without_duplicates(self):
        Category.objects.create(name=self.category.name, slug="existing-category")
        Tag.objects.create(name=self.tag.name, slug="existing-tag")
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.run_import(
                    self.source(items=[self.item()], tag_links=[(1, 20)]),
                    legacy_root=root,
                )

        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 1)
        self.assertEqual(Category.objects.get().legacy_k2_id, 10)
        self.assertEqual(Tag.objects.get().legacy_k2_id, 20)

    def test_duplicate_legacy_names_are_merged_and_keep_relations(self):
        duplicate_category = LegacyCategory(legacy_id=11, name=self.category.name)
        duplicate_tag = LegacyTag(legacy_id=21, name=self.tag.name)
        source = FakeK2Source(
            categories=[self.category, duplicate_category],
            tags=[self.tag, duplicate_tag],
            tag_links=[(1, duplicate_tag.legacy_id)],
            items=[self.item(category_id=duplicate_category.legacy_id)],
        )

        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                first_report = self.run_import(source, legacy_root=root)
                second_report = self.run_import(source, legacy_root=root)

        news = News.objects.get(legacy_k2_id=1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 1)
        self.assertEqual(news.category.legacy_k2_id, self.category.legacy_id)
        self.assertEqual(
            list(news.tags.values_list("legacy_k2_id", flat=True)),
            [self.tag.legacy_id],
        )
        self.assertEqual(first_report.counts.get("errors", 0), 0)
        self.assertEqual(second_report.counts.get("errors", 0), 0)
        self.assertEqual(first_report.counts["categories_merged"], 1)
        self.assertEqual(first_report.counts["tags_merged"], 1)

    def test_missing_image_on_update_preserves_existing_main_photo(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.run_import(self.source(items=[self.item()]), legacy_root=root)
                News.objects.filter(legacy_k2_id=1).update(
                    main_photo="news/main/already-imported.webp"
                )
                self.run_import(self.source(items=[self.item()]), legacy_root=root)

        self.assertEqual(
            News.objects.get(legacy_k2_id=1).main_photo.name,
            "news/main/already-imported.webp",
        )

    def test_media_copy_is_idempotent(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            legacy_root = Path(root)
            image_dir = legacy_root / "media" / "k2" / "items" / "src"
            image_dir.mkdir(parents=True)
            (image_dir / f"{k2_image_hash(1)}.jpg").write_bytes(b"legacy-image")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_import(self.source(items=[self.item()]), legacy_root=legacy_root)
                second_report = self.run_import(
                    self.source(items=[self.item()]),
                    legacy_root=legacy_root,
                )
                files = [path for path in Path(media_root).rglob("*") if path.is_file()]

        self.assertEqual(len(files), 1)
        self.assertEqual(second_report.counts.get("main_images_copied", 0), 0)

    def test_limit_resume_and_category_exclusion_are_honored(self):
        items = [self.item(legacy_id=number) for number in range(1, 5)]
        source = self.source(items=items)
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                report = K2Importer(
                    source,
                    legacy_root=Path(root),
                    legacy_timezone=MOSCOW,
                    apply=True,
                    now=self.now,
                ).run(limit=2, resume_from_id=2)

        self.assertEqual(report.counts["news_found"], 2)
        self.assertEqual(
            list(News.objects.order_by("legacy_k2_id").values_list("legacy_k2_id", flat=True)),
            [2, 3],
        )

        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                excluded_report = K2Importer(
                    source,
                    legacy_root=Path(root),
                    legacy_timezone=MOSCOW,
                    apply=True,
                    now=self.now,
                ).run(exclude_category_ids={self.category.legacy_id})
        self.assertEqual(excluded_report.counts.get("news_found", 0), 0)

    def test_inline_assets_are_rewritten_and_missing_assets_are_reported(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            legacy_root = Path(root)
            images = legacy_root / "images"
            images.mkdir()
            (images / "inside.jpg").write_bytes(b"inline-image")
            item = self.item(
                fulltext=(
                    '<p><img src="/images/inside.jpg">'
                    '<img src="/images/missing.jpg"></p>'
                )
            )
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(self.source(items=[item]), legacy_root=legacy_root)

        content = News.objects.get(legacy_k2_id=1).content
        self.assertIn("/media/legacy/k2/assets/images/inside-", content)
        self.assertIn('/images/missing.jpg', content)
        self.assertEqual(report.counts["inline_assets_copied"], 1)
        self.assertEqual(report.counts["inline_assets_missing"], 1)

    def test_legacy_lightbox_shortcode_is_removed_during_import(self):
        item = self.item(
            fulltext=(
                '<p>[lightbox src="images/shortcode/a12.jpg" width="310" '
                'lightbox="off"]&amp;nbsp;Читаемый текст</p>'
            )
        )
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.run_import(self.source(items=[item]), legacy_root=root)

        content = News.objects.get(legacy_k2_id=1).content
        self.assertEqual(content, '<p> Читаемый текст</p>')

    def test_repeated_inline_asset_is_hashed_once(self):
        with TemporaryDirectory() as root:
            legacy_root = Path(root)
            images = legacy_root / "images"
            images.mkdir()
            (images / "repeated.jpg").write_bytes(b"inline-image")
            migrator = K2AssetMigrator(
                legacy_root,
                ImportReport(dry_run=True),
                apply=False,
            )

            with patch(
                "news.k2_import.media.hashlib.sha256",
                wraps=hashlib.sha256,
            ) as sha256:
                first = migrator.rewrite_url("/images/repeated.jpg", entity_id=1)
                second = migrator.rewrite_url("/images/repeated.jpg", entity_id=2)

        self.assertEqual(first, second)
        self.assertEqual(sha256.call_count, 1)

    def test_malformed_legacy_html_cannot_close_the_article_layout(self):
        with TemporaryDirectory() as root:
            migrator = K2AssetMigrator(
                Path(root),
                ImportReport(dry_run=True),
                apply=False,
            )

            rewritten = migrator.rewrite_html(
                '</div><p>Текст <strong>материала</p></article>',
                entity_id=1,
            )

        self.assertEqual(rewritten, '<p>Текст <strong>материала</strong></p>')

    def test_unsafe_legacy_html_is_removed_before_publication(self):
        with TemporaryDirectory() as root:
            report = ImportReport(dry_run=True)
            migrator = K2AssetMigrator(
                Path(root),
                report,
                apply=False,
            )

            rewritten = migrator.rewrite_html(
                '<script>alert(1)</script>'
                '<p onclick="alert(2)">Безопасный текст</p>'
                '<a href="javascript:alert(3)">Ссылка</a>'
                '<img src="https://example.com/photo.jpg" onerror="alert(4)">',
                entity_id=77,
            )

        self.assertEqual(
            rewritten,
            '<p>Безопасный текст</p><a>Ссылка</a>'
            '<img src="https://example.com/photo.jpg">',
        )
        self.assertNotIn('script', rewritten)
        self.assertNotIn('onclick', rewritten)
        self.assertNotIn('javascript:', rewritten)
        self.assertNotIn('onerror', rewritten)
        self.assertEqual(report.counts['unsafe_html_removed'], 4)

    def test_main_image_directories_are_indexed_once_per_import(self):
        with TemporaryDirectory() as root:
            legacy_root = Path(root)
            image_dir = legacy_root / "media" / "k2" / "items" / "src"
            image_dir.mkdir(parents=True)
            for legacy_id in (1, 2):
                (image_dir / f"{k2_image_hash(legacy_id)}.jpg").write_bytes(
                    f"image-{legacy_id}".encode()
                )
            migrator = K2AssetMigrator(
                legacy_root,
                ImportReport(dry_run=True),
                apply=False,
            )

            with patch(
                "news.k2_import.media._K2MainImageIndex",
                wraps=k2_media._K2MainImageIndex,
            ) as image_index:
                self.assertIsNotNone(migrator.main_image_name(1))
                self.assertIsNotNone(migrator.main_image_name(2))

        self.assertEqual(image_index.call_count, 1)

    def test_missing_main_image_does_not_fail_import(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(self.source(items=[self.item()]), legacy_root=root)

        self.assertTrue(News.objects.filter(legacy_k2_id=1).exists())
        self.assertEqual(report.counts["news_without_image"], 1)
        self.assertEqual(report.counts.get("errors", 0), 0)

    def test_dry_run_does_not_write_database_or_media(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            legacy_root = Path(root)
            image_dir = legacy_root / "media" / "k2" / "items" / "src"
            image_dir.mkdir(parents=True)
            (image_dir / f"{k2_image_hash(1)}.png").write_bytes(b"legacy-image")
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(
                    self.source(items=[self.item()], tag_links=[(1, 20)]),
                    legacy_root=legacy_root,
                    apply=False,
                )
                written_files = list(Path(media_root).rglob("*"))

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)
        self.assertEqual(News.objects.count(), 0)
        self.assertEqual(written_files, [])
        self.assertEqual(report.counts["news_would_create"], 1)
        self.assertEqual(report.counts.get("main_images_copied", 0), 0)

    def test_newest_active_published_featured_item_wins(self):
        older = self.item(
            legacy_id=1,
            featured=True,
            publish_up=self.now - timedelta(days=2),
        )
        newer = self.item(
            legacy_id=2,
            featured=True,
            publish_up=self.now - timedelta(hours=1),
        )
        scheduled = self.item(
            legacy_id=3,
            featured=True,
            publish_up=self.now + timedelta(days=1),
        )
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(
                    self.source(items=[older, newer, scheduled]),
                    legacy_root=root,
                )

        self.assertEqual(report.selected_featured_legacy_id, 2)
        self.assertEqual(News.objects.get(is_featured=True).legacy_k2_id, 2)
        self.assertEqual(News.objects.filter(is_featured=True).count(), 1)

    def test_one_invalid_record_does_not_stop_following_items(self):
        broken = self.item(legacy_id=1, title="")
        valid = self.item(legacy_id=2)
        with TemporaryDirectory() as root, TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                report = self.run_import(
                    self.source(items=[broken, valid]),
                    legacy_root=root,
                )

        self.assertFalse(News.objects.filter(legacy_k2_id=1).exists())
        self.assertTrue(News.objects.filter(legacy_k2_id=2).exists())
        self.assertEqual(report.counts["errors"], 1)
        self.assertEqual(report.counts["news_skipped"], 1)


class K2CommandSafetyTests(TestCase):
    def test_command_defaults_to_dry_run(self):
        source = FakeK2Source(
            categories=[LegacyCategory(legacy_id=10, name="Общество")],
            items=[
                LegacyItem(
                    legacy_id=1,
                    title="Безопасная проверка",
                    category_id=10,
                    published=1,
                    publish_up="2026-09-01 10:00:00",
                )
            ],
        )
        output = StringIO()
        with (
            TemporaryDirectory() as root,
            TemporaryDirectory() as media_root,
            TemporaryDirectory() as report_dir,
            override_settings(MEDIA_ROOT=media_root),
            patch(
                "news.management.commands.import_k2.MySQLK2SourceConfig.from_environment",
                return_value=object(),
            ),
            patch(
                "news.management.commands.import_k2.MySQLK2Source",
                return_value=source,
            ),
        ):
            call_command(
                "import_k2",
                legacy_root=root,
                legacy_timezone="Europe/Moscow",
                report_dir=report_dir,
                stdout=output,
            )
            reports = list(Path(report_dir).glob("*.json"))
            media_files = [path for path in Path(media_root).rglob("*") if path.is_file()]

        self.assertIn("K2 import mode: DRY RUN", output.getvalue())
        self.assertEqual(len(reports), 1)
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(News.objects.count(), 0)
        self.assertEqual(media_files, [])
