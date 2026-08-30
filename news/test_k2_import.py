import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from news.models import Category, News, Tag


class K2ImportCommandTests(TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.base_path = Path(self.temporary_directory.name)
        self.source_path = self.base_path / "k2-export.json"
        self.legacy_media_root = self.base_path / "legacy-k2"
        self.target_media_root = self.base_path / "django-media"
        (self.legacy_media_root / "items" / "src").mkdir(parents=True)
        self.source_path.write_text(
            json.dumps(self.phpmyadmin_export(), ensure_ascii=False),
            encoding="utf-8",
        )

        digest = hashlib.md5(b"Image501").hexdigest()
        (self.legacy_media_root / "items" / "src" / f"{digest}.jpg").write_bytes(
            b"legacy-image"
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def phpmyadmin_export():
        return [
            {"type": "header", "version": "test"},
            {
                "type": "table",
                "name": "stavru_k2_categories",
                "data": [
                    {
                        "id": "10",
                        "name": "Общество",
                        "alias": "obshchestvo",
                        "description": "Новости общества",
                        "ordering": "1",
                        "published": "1",
                    },
                    {
                        "id": "11",
                        "name": "Архив",
                        "alias": "archive",
                        "ordering": "2",
                        "published": "0",
                    },
                ],
            },
            {
                "type": "table",
                "name": "stavru_k2_tags",
                "data": [
                    {"id": "21", "name": "Ставрополь", "published": "1"},
                    {"id": "22", "name": "Транспорт", "published": "1"},
                ],
            },
            {
                "type": "table",
                "name": "stavru_k2_tags_xref",
                "data": [
                    {"itemID": "501", "tagID": "21"},
                    {"itemID": "501", "tagID": "22"},
                    {"itemID": "502", "tagID": "21"},
                ],
            },
            {
                "type": "table",
                "name": "stavru_k2_items",
                "data": [
                    {
                        "id": "501",
                        "title": "Открыли новую дорогу",
                        "alias": "new-road",
                        "catid": "10",
                        "published": "1",
                        "introtext": "<p>Короткий анонс.</p>",
                        "fulltext": "<p>Полный текст материала.</p>",
                        "created": "2026-08-20 10:00:00",
                        "publish_up": "2026-08-21 09:00:00",
                        "publish_down": "0000-00-00 00:00:00",
                        "hits": "125",
                        "featured": "1",
                        "metadesc": "Описание для поиска",
                        "metakey": "дорога, Ставрополь",
                    },
                    {
                        "id": "502",
                        "title": "Будущая публикация",
                        "alias": "future-news",
                        "catid": "10",
                        "published": "1",
                        "introtext": "Будущий материал",
                        "fulltext": "",
                        "publish_up": "2030-01-01 12:00:00",
                        "hits": "4",
                        "featured": "1",
                    },
                    {
                        "id": "503",
                        "title": "Материал из корзины",
                        "alias": "trashed-news",
                        "catid": "11",
                        "published": "-2",
                        "trash": "1",
                    },
                ],
            },
        ]

    @override_settings(MEDIA_ROOT="/tmp/unused-k2-dry-run-media")
    def test_dry_run_validates_everything_and_rolls_back_database(self):
        output = StringIO()

        call_command(
            "import_k2",
            source=str(self.source_path),
            media_root=str(self.legacy_media_root),
            dry_run=True,
            stdout=output,
        )

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)
        self.assertEqual(News.objects.count(), 0)
        self.assertIn("DRY RUN", output.getvalue())
        self.assertIn("news_created: 2", output.getvalue())
        self.assertIn("images_found: 1", output.getvalue())
        self.assertIn("images_copied: 0", output.getvalue())

    def test_apply_imports_relations_image_and_is_idempotent(self):
        with override_settings(MEDIA_ROOT=self.target_media_root):
            first_output = StringIO()
            call_command(
                "import_k2",
                source=str(self.source_path),
                media_root=str(self.legacy_media_root),
                apply=True,
                stdout=first_output,
            )

            imported = News.objects.get(legacy_k2_id=501)
            scheduled = News.objects.get(legacy_k2_id=502)

            self.assertEqual(Category.objects.count(), 2)
            self.assertEqual(Tag.objects.count(), 2)
            self.assertEqual(News.objects.count(), 2)
            self.assertEqual(imported.category.legacy_k2_id, 10)
            self.assertSetEqual(
                set(imported.tags.values_list("legacy_k2_id", flat=True)),
                {21, 22},
            )
            self.assertEqual(imported.views, 125)
            self.assertIn("Короткий анонс", imported.content)
            self.assertIn("Полный текст", imported.content)
            self.assertEqual(imported.editorial_status, News.EditorialStatus.PUBLISHED)
            self.assertEqual(scheduled.editorial_status, News.EditorialStatus.SCHEDULED)
            self.assertTrue(imported.is_featured)
            self.assertFalse(scheduled.is_featured)
            self.assertTrue(imported.main_photo)
            self.assertTrue((self.target_media_root / imported.main_photo.name).is_file())
            self.assertIn("images_copied: 1", first_output.getvalue())
            self.assertIn("news_skipped_trash: 1", first_output.getvalue())

            second_output = StringIO()
            call_command(
                "import_k2",
                source=str(self.source_path),
                media_root=str(self.legacy_media_root),
                apply=True,
                stdout=second_output,
            )

        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(Tag.objects.count(), 2)
        self.assertEqual(News.objects.count(), 2)
        self.assertIn("news_created: 0", second_output.getvalue())
        self.assertIn("news_updated: 2", second_output.getvalue())
        self.assertIn("images_existing: 1", second_output.getvalue())

    def test_limit_only_restricts_news_not_reference_tables(self):
        with override_settings(MEDIA_ROOT=self.target_media_root):
            call_command(
                "import_k2",
                source=str(self.source_path),
                media_root=str(self.legacy_media_root),
                limit=1,
                apply=True,
                stdout=StringIO(),
            )

        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(Tag.objects.count(), 2)
        self.assertEqual(News.objects.count(), 1)
        self.assertTrue(News.objects.filter(legacy_k2_id=501).exists())
