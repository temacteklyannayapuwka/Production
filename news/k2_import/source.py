from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterator

from django.core.management.base import CommandError

from .domain import LegacyCategory, LegacyItem, LegacyTag


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class MySQLK2SourceConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    table_prefix: str
    charset: str = "utf8mb4"

    @classmethod
    def from_environment(cls) -> "MySQLK2SourceConfig":
        environment_names = {
            "host": "K2_DB_HOST",
            "database": "K2_DB_NAME",
            "user": "K2_DB_USER",
            "password": "K2_DB_PASSWORD",
            "table_prefix": "K2_DB_PREFIX",
        }
        required = {name: os.getenv(variable) for name, variable in environment_names.items()}
        missing = [environment_names[name] for name, value in required.items() if not value]
        if missing:
            raise CommandError(f"Missing required K2 database variables: {', '.join(missing)}")
        prefix = required["table_prefix"] or ""
        if not IDENTIFIER_PATTERN.fullmatch(prefix):
            raise CommandError("K2_DB_PREFIX may contain only ASCII letters, digits, and underscores.")
        try:
            port = int(os.getenv("K2_DB_PORT", "3306"))
        except ValueError as error:
            raise CommandError("K2_DB_PORT must be an integer.") from error
        charset = os.getenv("K2_DB_CHARSET", "utf8mb4")
        if not IDENTIFIER_PATTERN.fullmatch(charset):
            raise CommandError("K2_DB_CHARSET contains unsupported characters.")
        return cls(port=port, charset=charset, **required)


class MySQLK2Source:
    """Read-only DB-API adapter for a Joomla K2 MySQL/MariaDB database."""

    def __init__(self, config: MySQLK2SourceConfig, *, batch_size: int = 250):
        self.config = config
        self.batch_size = batch_size
        self.connection = None
        self._columns: dict[str, set[str]] = {}

    def __enter__(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as error:
            raise CommandError(
                "PyMySQL is required for K2 imports; install requirements-k2.txt."
            ) from error

        self.connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.config.charset,
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=120,
            write_timeout=10,
        )
        with self.connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection is not None:
            self.connection.close()

    def fetch_categories(self) -> list[LegacyCategory]:
        table = self._table("k2_categories")
        columns = self._table_columns(table)
        self._require_columns(table, columns, {"id", "name"})
        rows = self._fetch_all(table, columns, optional=(
            "id",
            "name",
            "alias",
            "description",
            "ordering",
            "published",
        ))
        return [
            LegacyCategory(
                legacy_id=int(row["id"]),
                name=str(row["name"] or ""),
                alias=str(row.get("alias") or ""),
                description=str(row.get("description") or ""),
                ordering=_as_int(row.get("ordering")),
                published=_as_bool(row.get("published"), default=True),
            )
            for row in rows
        ]

    def fetch_tags(self) -> list[LegacyTag]:
        table = self._table("k2_tags")
        columns = self._table_columns(table)
        self._require_columns(table, columns, {"id", "name"})
        rows = self._fetch_all(
            table,
            columns,
            optional=("id", "name", "alias", "slug", "published"),
        )
        return [
            LegacyTag(
                legacy_id=int(row["id"]),
                name=str(row["name"] or ""),
                alias=str(row.get("alias") or row.get("slug") or ""),
                published=_as_bool(row.get("published"), default=True),
            )
            for row in rows
        ]

    def fetch_tag_links(self) -> list[tuple[int, int]]:
        table = self._table("k2_tags_xref")
        columns = self._table_columns(table)
        self._require_columns(table, columns, {"itemID", "tagID"})
        query = f"SELECT `itemID`, `tagID` FROM `{table}` ORDER BY `itemID`, `tagID`"
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return [(int(row["itemID"]), int(row["tagID"])) for row in cursor.fetchall()]

    def iter_items(
        self,
        *,
        limit: int | None = None,
        resume_from_id: int | None = None,
        exclude_category_ids: set[int] | None = None,
    ) -> Iterator[LegacyItem]:
        table = self._table("k2_items")
        columns = self._table_columns(table)
        self._require_columns(table, columns, {"id", "title", "catid", "published"})
        requested = (
            "id",
            "title",
            "alias",
            "catid",
            "published",
            "introtext",
            "fulltext",
            "created",
            "publish_up",
            "publish_down",
            "hits",
            "featured",
            "metadesc",
            "metakey",
            "trash",
        )
        selected = [column for column in requested if column in columns]
        query = f"SELECT {', '.join(f'`{column}`' for column in selected)} FROM `{table}`"
        clauses = ["`published` <> -2"]
        params: list[int] = []
        if "trash" in columns:
            clauses.append("COALESCE(`trash`, 0) = 0")
        if resume_from_id is not None:
            clauses.append("`id` >= %s")
            params.append(resume_from_id)
        excluded = sorted(exclude_category_ids or set())
        if excluded:
            clauses.append(f"`catid` NOT IN ({', '.join(['%s'] * len(excluded))})")
            params.extend(excluded)
        query += f" WHERE {' AND '.join(clauses)} ORDER BY `id`"
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            while rows := cursor.fetchmany(self.batch_size):
                for row in rows:
                    yield LegacyItem(
                        legacy_id=int(row["id"]),
                        title=str(row["title"] or ""),
                        alias=str(row.get("alias") or ""),
                        category_id=_as_optional_int(row.get("catid")),
                        published=_as_int(row.get("published")),
                        introtext=str(row.get("introtext") or ""),
                        fulltext=str(row.get("fulltext") or ""),
                        created=row.get("created"),
                        publish_up=row.get("publish_up"),
                        publish_down=row.get("publish_down"),
                        hits=_as_int(row.get("hits")),
                        featured=_as_bool(row.get("featured")),
                        meta_description=str(row.get("metadesc") or ""),
                        meta_keywords=str(row.get("metakey") or ""),
                        trashed=_as_bool(row.get("trash")),
                    )

    def _table(self, suffix: str) -> str:
        return f"{self.config.table_prefix}{suffix}"

    def _table_columns(self, table: str) -> set[str]:
        if table not in self._columns:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                self._columns[table] = {str(row["Field"]) for row in cursor.fetchall()}
        return self._columns[table]

    @staticmethod
    def _require_columns(table: str, columns: set[str], required: set[str]) -> None:
        missing = sorted(required - columns)
        if missing:
            raise CommandError(f"Legacy table {table} is missing columns: {', '.join(missing)}")

    def _fetch_all(self, table: str, columns: set[str], *, optional: tuple[str, ...]):
        selected = [column for column in optional if column in columns]
        query = f"SELECT {', '.join(f'`{column}`' for column in selected)} FROM `{table}` ORDER BY `id`"
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    return _as_int(value)


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return _as_int(value) == 1
