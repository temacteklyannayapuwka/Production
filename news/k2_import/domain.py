from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from django.utils import timezone


@dataclass(frozen=True)
class LegacyCategory:
    legacy_id: int
    name: str
    alias: str = ""
    description: str = ""
    ordering: int = 0
    published: bool = True


@dataclass(frozen=True)
class LegacyTag:
    legacy_id: int
    name: str
    alias: str = ""
    published: bool = True


@dataclass(frozen=True)
class LegacyItem:
    legacy_id: int
    title: str
    alias: str = ""
    category_id: int | None = None
    published: int = 0
    introtext: str = ""
    fulltext: str = ""
    created: Any = None
    publish_up: Any = None
    publish_down: Any = None
    hits: int = 0
    featured: bool = False
    meta_description: str = ""
    meta_keywords: str = ""
    trashed: bool = False


@dataclass(frozen=True)
class PublicationValues:
    editorial_status: str
    is_published: bool
    date_start: datetime
    date_end: datetime | None


@dataclass
class ImportReport:
    dry_run: bool
    started_at: datetime = field(default_factory=timezone.now)
    finished_at: datetime | None = None
    counts: dict[str, int] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    selected_featured_legacy_id: int | None = None
    last_successful_legacy_id: int | None = None

    def increment(self, name: str, amount: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + amount

    def issue(
        self,
        kind: str,
        message: str,
        *,
        entity: str | None = None,
        legacy_id: int | None = None,
    ) -> None:
        self.issues.append(
            {
                "kind": kind,
                "entity": entity,
                "legacy_id": legacy_id,
                "message": str(message)[:1000],
            }
        )
        self.increment(kind)

    def error(self, entity: str, legacy_id: int | None, error: Exception | str) -> None:
        self.errors.append(
            {
                "entity": entity,
                "legacy_id": legacy_id,
                "error_type": type(error).__name__ if isinstance(error, Exception) else "Error",
                "message": str(error)[:1000],
            }
        )
        self.increment("errors")

    def finish(self) -> None:
        self.finished_at = timezone.now()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["started_at"] = self.started_at.isoformat()
        payload["finished_at"] = (
            self.finished_at.isoformat() if self.finished_at is not None else None
        )
        return payload

    def write(self, report_dir: Path) -> tuple[Path, Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.started_at.strftime("%Y%m%d-%H%M%S-%f")
        mode = "dry-run" if self.dry_run else "apply"
        report_path = report_dir / f"k2-import-{mode}-{timestamp}.json"
        errors_path = report_dir / f"k2-import-{mode}-{timestamp}.errors.log"
        report_path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        error_lines = [
            f"{item['entity']}:{item['legacy_id'] or '-'} "
            f"{item['error_type']}: {item['message']}"
            for item in self.errors
        ]
        errors_path.write_text(
            "\n".join(error_lines) + ("\n" if error_lines else ""),
            encoding="utf-8",
        )
        return report_path, errors_path
