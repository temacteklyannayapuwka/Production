"""Central search and social metadata for public Stavplus pages."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin, urlsplit

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator


SITE_NAME = "Ставрополь+"
DEFAULT_DESCRIPTION = (
    "Ставрополь+ — новости Ставрополя, Ставропольского края, России и мира."
)
DEFAULT_IMAGE_PATH = "hero/stavropol-aerial.webp"
LOGO_PATH = "brand/stavplus-mark.svg"


def public_origin() -> str:
    """Return the configured canonical origin without a trailing slash."""
    return settings.PUBLIC_SITE_URL.rstrip("/")


def absolute_url(value: str) -> str:
    """Convert a local path to a canonical absolute URL.

    The public origin comes from trusted settings rather than the request Host
    header, avoiding incorrect canonicals on the redesign subdomain and host
    header poisoning.
    """
    value = str(value or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    return urljoin(f"{public_origin()}/", value.lstrip("/"))


def _plain_text(value: str, *, limit: int = 160) -> str:
    text = html.unescape(strip_tags(str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return Truncator(text).chars(limit) if text else ""


def _brand_title(value: str) -> str:
    title = _plain_text(value, limit=200) or SITE_NAME
    if SITE_NAME.casefold() not in title.casefold():
        title = f"{title} — {SITE_NAME}"
    return title


def _organization() -> dict:
    return {
        "@type": "NewsMediaOrganization",
        "@id": f"{public_origin()}/#organization",
        "name": SITE_NAME,
        "url": f"{public_origin()}/",
        "logo": {
            "@type": "ImageObject",
            "url": absolute_url(static(LOGO_PATH)),
            "width": 64,
            "height": 64,
        },
    }


def _breadcrumb_schema(items: list[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": absolute_url(path),
            }
            for position, (name, path) in enumerate(items, start=1)
        ],
    }


def _page_number(page_obj) -> int:
    return page_obj.number if page_obj and page_obj.number > 1 else 1


def _pagination_path(path: str, page_obj) -> str:
    page_number = _page_number(page_obj)
    return f"{path}?page={page_number}" if page_number > 1 else path


def _seo_data(
    *,
    title: str,
    description: str,
    path: str,
    robots: str = "index,follow",
    image: str = "",
    page_type: str = "website",
    breadcrumbs: list[tuple[str, str]] | None = None,
    additional_schema: dict | None = None,
    published_time: str = "",
    modified_time: str = "",
    section: str = "",
) -> dict:
    canonical_url = absolute_url(path)
    description = _plain_text(description) or DEFAULT_DESCRIPTION
    graph = [_organization()]
    if breadcrumbs:
        graph.append(_breadcrumb_schema(breadcrumbs))
    if additional_schema:
        graph.append(additional_schema)
    return {
        "title": _brand_title(title),
        "description": description,
        "canonical_url": canonical_url,
        "robots": robots,
        "page_type": page_type,
        "image_url": absolute_url(image or static(DEFAULT_IMAGE_PATH)),
        "published_time": published_time,
        "modified_time": modified_time,
        "section": section,
        "structured_data": {
            "@context": "https://schema.org",
            "@graph": graph,
        },
    }


def home_seo() -> dict:
    return _seo_data(
        title="Новости Ставрополя и Ставропольского края",
        description=DEFAULT_DESCRIPTION,
        path=reverse("index"),
    )


def category_seo(category, page_obj) -> dict:
    page_number = _page_number(page_obj)
    suffix = f" — страница {page_number}" if page_number > 1 else ""
    path = reverse("category", kwargs={"category_slug": category.slug})
    canonical_path = _pagination_path(path, page_obj)
    description = category.description or (
        f"Свежие новости раздела «{category.name}» на портале Ставрополь+."
    )
    if page_number > 1:
        description = f"{description} Страница {page_number}."
    return _seo_data(
        title=f"{category.name}: новости Ставрополя и края{suffix}",
        description=description,
        path=canonical_path,
        breadcrumbs=[("Главная", reverse("index")), (category.name, path)],
    )


def tag_seo(tag, page_obj) -> dict:
    page_number = _page_number(page_obj)
    suffix = f" — страница {page_number}" if page_number > 1 else ""
    path = reverse("tag", kwargs={"tag_slug": tag.slug})
    canonical_path = _pagination_path(path, page_obj)
    description = tag.description or (
        f"Новости и материалы по теме «{tag.name}» на портале Ставрополь+."
    )
    if page_number > 1:
        description = f"{description} Страница {page_number}."
    return _seo_data(
        title=f"{tag.name}: новости и материалы{suffix}",
        description=description,
        path=canonical_path,
        breadcrumbs=[("Главная", reverse("index")), (f"Тема: {tag.name}", path)],
    )


def search_seo(query: str) -> dict:
    title = f"Поиск: {query}" if query else "Поиск по новостям"
    description = (
        f"Результаты поиска по запросу «{query}» на портале Ставрополь+."
        if query
        else "Поиск по новостям и материалам портала Ставрополь+."
    )
    return _seo_data(
        title=title,
        description=description,
        path=reverse("search"),
        robots="noindex,follow",
    )


def _article_image(article) -> str:
    if article.main_photo:
        try:
            return article.main_photo.url
        except ValueError:
            pass
    return static(DEFAULT_IMAGE_PATH)


def article_seo(article) -> dict:
    path = article.get_absolute_url()
    canonical_url = absolute_url(path)
    image_url = absolute_url(_article_image(article))
    description = article.meta_description or article.excerpt or article.title
    article_schema = {
        "@type": "NewsArticle",
        "@id": f"{canonical_url}#article",
        "headline": _plain_text(article.title, limit=220),
        "description": _plain_text(description),
        "image": [image_url],
        "datePublished": article.date_start.isoformat(),
        "dateModified": article.updated_at.isoformat(),
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "author": {"@type": "Organization", "name": SITE_NAME},
        "publisher": {"@id": f"{public_origin()}/#organization"},
        "url": canonical_url,
    }
    if article.category:
        article_schema["articleSection"] = article.category.name
    active_tags = [tag.name for tag in article.tags.all() if tag.is_active]
    if active_tags:
        article_schema["keywords"] = active_tags
    try:
        imported_item = article.ai_import
    except ObjectDoesNotExist:
        imported_item = None
    if imported_item and imported_item.source_url:
        article_schema["isBasedOn"] = imported_item.source_url

    breadcrumbs = [("Главная", reverse("index"))]
    if article.category:
        breadcrumbs.append(
            (
                article.category.name,
                reverse("category", kwargs={"category_slug": article.category.slug}),
            )
        )
    breadcrumbs.append((article.title, path))
    return _seo_data(
        title=article.meta_title or article.title,
        description=description,
        path=path,
        image=image_url,
        page_type="article",
        breadcrumbs=breadcrumbs,
        additional_schema=article_schema,
        published_time=article.date_start.isoformat(),
        modified_time=article.updated_at.isoformat(),
        section=article.category.name if article.category else "Новости",
    )


def not_found_seo(path: str) -> dict:
    return _seo_data(
        title="Страница не найдена",
        description=(
            "Запрошенная страница не найдена. Перейдите на главную страницу "
            "Ставрополь+, чтобы открыть актуальные новости."
        ),
        path=path,
        robots="noindex,follow",
    )
