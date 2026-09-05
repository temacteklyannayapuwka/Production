from __future__ import annotations

import hashlib
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.files import File
from django.core.files.storage import default_storage

from .domain import ImportReport


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
LOCAL_ASSET_PREFIXES = ("/media/k2/", "/images/")


def k2_image_hash(legacy_id: int) -> str:
    return hashlib.md5(f"Image{legacy_id}".encode(), usedforsecurity=False).hexdigest()


def find_k2_main_image(legacy_root: Path, legacy_id: int) -> Path | None:
    """Find the best available K2 image without assuming one extension."""
    image_hash = k2_image_hash(legacy_id)
    src_dir = legacy_root / "media" / "k2" / "items" / "src"
    cache_dir = legacy_root / "media" / "k2" / "items" / "cache"

    src_candidates = _matching_files(src_dir, image_hash)
    if src_candidates:
        return src_candidates[0]

    cache_candidates = _matching_files(cache_dir, image_hash, prefix=True)
    preferred_suffixes = ("_xl", "_l", "_generic")
    for suffix in preferred_suffixes:
        match = next(
            (path for path in cache_candidates if path.stem.casefold() == f"{image_hash}{suffix}"),
            None,
        )
        if match:
            return match
    return cache_candidates[0] if cache_candidates else None


def _matching_files(directory: Path, stem: str, *, prefix: bool = False) -> list[Path]:
    if not directory.is_dir():
        return []
    target = stem.casefold()
    matches = []
    for path in directory.iterdir():
        candidate = path.stem.casefold()
        stem_matches = candidate.startswith(f"{target}_") if prefix else candidate == target
        if path.is_file() and stem_matches and path.suffix.casefold() in IMAGE_EXTENSIONS:
            matches.append(path)
    return sorted(matches, key=lambda path: path.name.casefold())


class K2AssetMigrator:
    def __init__(
        self,
        legacy_root: Path,
        report: ImportReport,
        *,
        apply: bool,
        storage=default_storage,
    ):
        self.legacy_root = legacy_root.resolve()
        self.report = report
        self.apply = apply
        self.storage = storage
        self._seen_inline_found: set[Path] = set()
        self._seen_inline_missing: set[str] = set()

    def main_image_name(self, legacy_id: int) -> str | None:
        source = find_k2_main_image(self.legacy_root, legacy_id)
        if source is None:
            self.report.increment("news_without_image")
            return None

        self.report.increment("main_images_found")
        destination = self._hashed_destination(source, f"legacy/k2/items/{legacy_id}")
        if self.apply and self._copy_once(source, destination):
            self.report.increment("main_images_copied")
        return destination

    def rewrite_html(self, html: str, *, entity_id: int) -> str:
        if not html:
            return ""
        parser = _AssetHTMLRewriter(self, entity_id)
        try:
            parser.feed(html)
            parser.close()
        except Exception as error:
            self.report.error("inline_html", entity_id, error)
            return html
        return parser.output

    def rewrite_url(self, value: str, *, entity_id: int) -> str:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return value
        decoded_path = unquote(parsed.path)
        normalized = f"/{decoded_path.lstrip('/')}"
        if not normalized.casefold().startswith(LOCAL_ASSET_PREFIXES):
            return value

        source = (self.legacy_root / normalized.lstrip("/")).resolve()
        if not source.is_relative_to(self.legacy_root) or not source.is_file():
            if value not in self._seen_inline_missing:
                self._seen_inline_missing.add(value)
                self.report.increment("inline_assets_missing")
                self.report.issue(
                    "missing_inline_asset_references",
                    value,
                    entity="news",
                    legacy_id=entity_id,
                )
            return value

        if source not in self._seen_inline_found:
            self._seen_inline_found.add(source)
            self.report.increment("inline_assets_found")
        relative_parent = source.relative_to(self.legacy_root).parent.as_posix()
        destination = self._hashed_destination(
            source,
            f"legacy/k2/assets/{relative_parent}",
        )
        if self.apply and self._copy_once(source, destination):
            self.report.increment("inline_assets_copied")
        rewritten = self.storage.url(destination)
        return f"{rewritten}#{parsed.fragment}" if parsed.fragment else rewritten

    def _hashed_destination(self, source: Path, parent: str) -> str:
        digest_builder = hashlib.sha256()
        with source.open("rb") as source_file:
            while chunk := source_file.read(1024 * 1024):
                digest_builder.update(chunk)
        digest = digest_builder.hexdigest()[:12]
        safe_stem = source.stem[:100] or "asset"
        return f"{parent}/{safe_stem}-{digest}{source.suffix.casefold()}"

    def _copy_once(self, source: Path, destination: str) -> bool:
        if self.storage.exists(destination):
            return False
        with source.open("rb") as source_file:
            saved_name = self.storage.save(destination, File(source_file))
        if saved_name != destination:
            raise RuntimeError(f"storage changed deterministic asset name {destination!r}")
        return True


class _AssetHTMLRewriter(HTMLParser):
    def __init__(self, migrator: K2AssetMigrator, entity_id: int):
        super().__init__(convert_charrefs=False)
        self.migrator = migrator
        self.entity_id = entity_id
        self.parts: list[str] = []

    @property
    def output(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag, attrs):
        self._handle_tag(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._handle_tag(tag, attrs, self_closing=True)

    def _handle_tag(self, tag, attrs, *, self_closing):
        rewritten_attrs = []
        changed = False
        for name, value in attrs:
            rewritten = value
            if value is not None and name.casefold() in {"src", "href"}:
                rewritten = self.migrator.rewrite_url(value, entity_id=self.entity_id)
                changed = changed or rewritten != value
            rewritten_attrs.append((name, rewritten))

        if not changed and self.get_starttag_text():
            self.parts.append(self.get_starttag_text())
            return

        rendered_attrs = []
        for name, value in rewritten_attrs:
            if value is None:
                rendered_attrs.append(name)
            else:
                rendered_attrs.append(f'{name}="{escape(value, quote=True)}"')
        suffix = " /" if self_closing else ""
        attributes = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        self.parts.append(f"<{tag}{attributes}{suffix}>")

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data):
        self.parts.append(f"<?{data}>")

    def unknown_decl(self, data):
        self.parts.append(f"<![{data}]>")
