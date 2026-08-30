"""Safely import a structured Joomla K2 JSON export."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.importers.k2 import K2Dataset, K2Importer, K2ImportError


class Command(BaseCommand):
    help = "Импортирует Joomla K2 из JSON-выгрузки phpMyAdmin без дублей."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Путь к JSON-выгрузке K2.")
        parser.add_argument(
            "--media-root",
            help="Путь к распакованному каталогу media/k2 для поиска изображений.",
        )
        parser.add_argument("--limit", type=int, help="Импортировать только первые N новостей.")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="Проверить и откатить БД.")
        mode.add_argument("--apply", action="store_true", help="Применить импорт.")

    def handle(self, *args, **options):
        source = Path(options["source"]).expanduser().resolve()
        if not source.is_file():
            raise CommandError(f"JSON-выгрузка не найдена: {source}")

        media_root = None
        if options["media_root"]:
            media_root = Path(options["media_root"]).expanduser().resolve()
            if not media_root.is_dir():
                raise CommandError(f"Каталог media/k2 не найден: {media_root}")

        limit = options["limit"]
        if limit is not None and limit <= 0:
            raise CommandError("--limit должен быть положительным числом.")

        try:
            dataset = K2Dataset.from_json(source)
            importer = K2Importer(
                dataset,
                media_root=media_root,
                copy_images=options["apply"],
                limit=limit,
            )
            try:
                with transaction.atomic():
                    stats = importer.run()
                    if options["dry_run"]:
                        transaction.set_rollback(True)
            except Exception:
                importer.cleanup_written_files()
                raise
        except K2ImportError as error:
            raise CommandError(str(error)) from error

        mode = "DRY RUN — изменения отменены" if options["dry_run"] else "IMPORT APPLIED"
        self.stdout.write(self.style.SUCCESS(mode))
        for key in (
            "categories_created",
            "categories_updated",
            "tags_created",
            "tags_updated",
            "news_created",
            "news_updated",
            "news_skipped_trash",
            "images_found",
            "images_copied",
            "images_existing",
            "images_missing",
            "missing_category_links",
            "missing_tag_links",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

