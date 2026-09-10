from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from news.k2_import import K2Importer, MySQLK2Source, MySQLK2SourceConfig


class Command(BaseCommand):
    help = "Safely analyze or import Joomla K2 content into StavPlus."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--apply",
            action="store_true",
            help="Write Django records and copy media. Without this flag the command is read-only.",
        )
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicitly select the default read-only analysis mode.",
        )
        parser.add_argument("--limit", type=int, help="Analyze or import at most this many items.")
        parser.add_argument(
            "--resume-from-id",
            type=int,
            help="Resume inclusively from this K2 item ID; reruns are idempotent.",
        )
        parser.add_argument(
            "--exclude-category",
            action="append",
            type=int,
            default=[],
            metavar="K2_ID",
            help="Exclude a legacy K2 category ID. Repeat for multiple categories.",
        )
        parser.add_argument(
            "--legacy-root",
            help="Path to the Joomla root containing media/k2/ and images/.",
        )
        parser.add_argument(
            "--legacy-timezone",
            help="IANA timezone used by Joomla, for example Europe/Moscow.",
        )
        parser.add_argument(
            "--report-dir",
            help="Directory for the JSON report and sanitized error log.",
        )

    def handle(self, *args, **options):
        self._validate_options(options)
        apply = options["apply"]
        legacy_root_value = options["legacy_root"] or os.getenv("K2_MEDIA_ROOT")
        if not legacy_root_value:
            raise CommandError(
                "Provide an existing Joomla root with --legacy-root or K2_MEDIA_ROOT."
            )
        legacy_root = Path(legacy_root_value).expanduser()
        if not legacy_root.is_dir():
            raise CommandError(
                "Provide an existing Joomla root with --legacy-root or K2_MEDIA_ROOT."
            )

        timezone_name = options["legacy_timezone"] or os.getenv("K2_TIME_ZONE")
        if not timezone_name:
            raise CommandError(
                "Set --legacy-timezone or K2_TIME_ZONE explicitly; the importer will not guess."
            )
        try:
            legacy_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise CommandError(f"Unknown legacy timezone: {timezone_name}") from error

        report_dir = Path(
            options["report_dir"]
            or os.getenv("K2_REPORT_DIR", "")
            or Path(settings.BASE_DIR) / "var" / "k2-import"
        ).expanduser()
        config = MySQLK2SourceConfig.from_environment()

        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(f"K2 import mode: {mode}")
        if not apply:
            self.stdout.write("Database records and MEDIA storage will not be changed.")

        try:
            with MySQLK2Source(config) as source:
                report = K2Importer(
                    source,
                    legacy_root=legacy_root,
                    legacy_timezone=legacy_timezone,
                    apply=apply,
                ).run(
                    limit=options["limit"],
                    resume_from_id=options["resume_from_id"],
                    exclude_category_ids=set(options["exclude_category"]),
                )
        except CommandError:
            raise
        except Exception as error:
            message = str(error)
            if config.password:
                message = message.replace(config.password, "[REDACTED]")
            raise CommandError(
                f"K2 source could not be read ({type(error).__name__}: {message[:300]})."
            ) from error

        report_path, errors_path = report.write(report_dir)
        self._print_report(report, report_path, errors_path)

    @staticmethod
    def _validate_options(options):
        if options["limit"] is not None and options["limit"] < 1:
            raise CommandError("--limit must be greater than zero.")
        if options["resume_from_id"] is not None and options["resume_from_id"] < 0:
            raise CommandError("--resume-from-id cannot be negative.")

    def _print_report(self, report, report_path: Path, errors_path: Path) -> None:
        counts = report.counts
        rows = (
            ("Найдено новостей", counts.get("news_found", 0)),
            ("Импортировано", counts.get("news_imported", 0)),
            ("Обновлено", counts.get("news_updated", 0)),
            ("Пропущено", counts.get("news_skipped", 0)),
            ("Категорий создано", counts.get("categories_created", 0)),
            ("Категорий обновлено", counts.get("categories_updated", 0)),
            ("Тегов создано", counts.get("tags_created", 0)),
            ("Тегов обновлено", counts.get("tags_updated", 0)),
            ("Изображений найдено", counts.get("main_images_found", 0)),
            ("Изображений скопировано", counts.get("main_images_copied", 0)),
            ("Новостей без изображения", counts.get("news_without_image", 0)),
            ("Inline assets скопировано", counts.get("inline_assets_copied", 0)),
            ("Inline assets отсутствует", counts.get("inline_assets_missing", 0)),
            ("Ошибок", counts.get("errors", 0)),
        )
        for label, value in rows:
            self.stdout.write(f"{label}: {value}")
        if report.dry_run:
            self.stdout.write(
                f"Будет создано/обновлено новостей: "
                f"{counts.get('news_would_create', 0)}/{counts.get('news_would_update', 0)}"
            )
        if report.selected_featured_legacy_id is not None:
            self.stdout.write(
                f"Выбрана главная legacy news: {report.selected_featured_legacy_id}"
            )
        if report.last_successful_legacy_id is not None:
            self.stdout.write(
                f"Последний успешно обработанный ID: {report.last_successful_legacy_id}"
            )
        self.stdout.write(self.style.SUCCESS(f"JSON report: {report_path}"))
        self.stdout.write(f"Error log: {errors_path}")
