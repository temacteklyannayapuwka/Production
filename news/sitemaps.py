"""Canonical public and Google News sitemaps."""

from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

from django.contrib.sitemaps import Sitemap
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.db.models import Exists, Max, OuterRef, Q
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from .models import Category, News, Tag
from .seo import public_origin


def public_news_queryset():
    now = timezone.now()
    return (
        News.objects.filter(is_published=True, date_start__lte=now)
        .filter(Q(date_end__isnull=True) | Q(date_end__gte=now))
        .order_by("-date_start", "-pk")
    )


class HomeSitemap(Sitemap):
    protocol = "https"
    changefreq = "hourly"
    priority = 1.0

    def items(self):
        return ["home"]

    def location(self, item):
        return reverse("index")


class NewsSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return public_news_queryset()

    def lastmod(self, item):
        return item.updated_at


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.7

    def items(self):
        now = timezone.now()
        public_items = public_news_queryset().filter(category_id=OuterRef("pk"))
        public_filter = Q(news__is_published=True, news__date_start__lte=now) & (
            Q(news__date_end__isnull=True) | Q(news__date_end__gte=now)
        )
        return (
            Category.objects.filter(is_active=True)
            .annotate(has_public_news=Exists(public_items))
            .filter(has_public_news=True)
            .annotate(last_public_update=Max("news__updated_at", filter=public_filter))
            .order_by("order", "name")
        )

    def location(self, item):
        return reverse("category", kwargs={"category_slug": item.slug})

    def lastmod(self, item):
        return item.last_public_update


class TagSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.6

    def items(self):
        now = timezone.now()
        public_items = public_news_queryset().filter(tags__pk=OuterRef("pk"))
        public_filter = Q(
            news_items__is_published=True,
            news_items__date_start__lte=now,
        ) & (
            Q(news_items__date_end__isnull=True)
            | Q(news_items__date_end__gte=now)
        )
        return (
            Tag.objects.filter(is_active=True)
            .annotate(has_public_news=Exists(public_items))
            .filter(has_public_news=True)
            .annotate(
                last_public_update=Max(
                    "news_items__updated_at",
                    filter=public_filter,
                )
            )
            .order_by("name")
        )

    def location(self, item):
        return reverse("tag", kwargs={"tag_slug": item.slug})

    def lastmod(self, item):
        return item.last_public_update


class RecentNewsSitemap(NewsSitemap):
    """Google News feed: at most 1,000 public stories from the last two days."""

    limit = 1000

    def items(self):
        cutoff = timezone.now() - timedelta(days=2)
        return public_news_queryset().filter(date_start__gte=cutoff)[:1000]


PUBLIC_SITEMAPS = {
    "home": HomeSitemap,
    "news": NewsSitemap,
    "categories": CategorySitemap,
    "tags": TagSitemap,
}

GOOGLE_NEWS_SITEMAPS = {"recent_news": RecentNewsSitemap}


def sitemap_response(request, sitemaps, *, template_name="sitemap.xml"):
    """Render Django Sitemap classes against the configured public origin."""
    parsed_origin = urlsplit(public_origin())
    site = SimpleNamespace(domain=parsed_origin.netloc, name="Ставрополь+")
    page = request.GET.get("p", 1)
    urls = []
    try:
        for sitemap_class in sitemaps.values():
            sitemap = sitemap_class()
            urls.extend(
                sitemap.get_urls(
                    page=page,
                    site=site,
                    protocol=parsed_origin.scheme,
                )
            )
    except EmptyPage as error:
        raise Http404(f"Sitemap page {page} is empty") from error
    except PageNotAnInteger as error:
        raise Http404(f"Invalid sitemap page {page}") from error

    response = TemplateResponse(
        request,
        template_name,
        {"urlset": urls},
        content_type="application/xml",
    )
    response["X-Robots-Tag"] = "noindex, follow"
    return response
