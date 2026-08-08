import mimetypes
from pathlib import PurePosixPath

from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Category, News


def _serve_javascript_asset(static_prefix, asset_path):
    """Return a whitelisted JavaScript asset through Django.

    The current ISPmanager Nginx configuration only serves a fixed list of
    extensions directly. It omits JavaScript, so these requests reach Django
    instead. The narrow fallbacks keep the admin interface and public menu
    usable without exposing arbitrary project files.
    """
    relative_path = PurePosixPath(asset_path)
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or relative_path.suffix not in {".js", ".mjs", ".map"}
    ):
        raise Http404("Static asset not found")

    source_name = "/".join(
        part for part in (static_prefix.strip("/"), relative_path.as_posix()) if part
    )
    source_path = finders.find(source_name)
    if not source_path:
        raise Http404("Static asset not found")

    content_type, _ = mimetypes.guess_type(source_path)
    response = FileResponse(
        open(source_path, "rb"),
        content_type=content_type or "application/javascript",
    )
    response["Cache-Control"] = "public, max-age=86400"
    return response


def serve_unfold_javascript(request, asset_path):
    return _serve_javascript_asset("unfold/js", asset_path)


def serve_admin_javascript(request, asset_path):
    return _serve_javascript_asset("admin/js", asset_path)


def serve_ckeditor_javascript(request, asset_path):
    return _serve_javascript_asset("ckeditor", asset_path)


def serve_public_javascript(request):
    """Serve the public site's single interactive bundle through Django.

    ISPmanager's standard Nginx configuration in this project does not include
    the ``.js`` extension in its static-file location. As a result,
    ``/static/news-site.js`` is proxied to Django and used to return 404,
    leaving the menu button without its click handler. This explicit route
    keeps the workaround small and does not expose arbitrary static files.
    """
    return _serve_javascript_asset("", "news-site.js")


def published_news():
    """News that may be shown publicly at the current moment."""
    now = timezone.now()
    return (
        News.objects.select_related("category")
        .filter(is_published=True, date_start__lte=now)
        .filter(Q(date_end__isnull=True) | Q(date_end__gte=now))
        .order_by("-is_featured", "-date_start", "-created_at")
    )


def navigation_categories():
    return Category.objects.filter(is_active=True).order_by("order", "name")


def shared_context(**extra):
    context = {"navigation_categories": navigation_categories()}
    context.update(extra)
    return context


def paginate(request, queryset, per_page=20):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def index(request):
    news = published_news()
    return render(
        request,
        "index.html",
        shared_context(
            hero_news=news.first(),
            card_news=news[1:5],
            headline_news=news[5:13],
            popular_news=news.order_by("-views", "-date_start")[:5],
        ),
    )


def category_page(request, category_slug):
    category = get_object_or_404(
        Category.objects.filter(is_active=True), slug=category_slug
    )
    page_obj = paginate(request, published_news().filter(category=category))
    return render(
        request,
        "category.html",
        shared_context(
            active_category=category,
            category_news=page_obj,
            page_obj=page_obj,
            popular_news=published_news().order_by("-views", "-date_start")[:5],
        ),
    )


def search(request):
    query = request.GET.get("q", "").strip()
    results = published_news().none()
    if query:
        results = published_news().filter(
            Q(title__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(content__icontains=query)
            | Q(category__name__icontains=query)
        )
    page_obj = paginate(request, results)
    return render(
        request,
        "search.html",
        shared_context(query=query, search_results=page_obj, page_obj=page_obj),
    )


def news_detail(request, slug):
    article = get_object_or_404(published_news(), slug=slug)
    News.objects.filter(pk=article.pk).update(views=F("views") + 1)
    article.refresh_from_db(fields=["views"])
    recent_news = published_news().exclude(pk=article.pk)[:5]
    return render(
        request,
        "article.html",
        shared_context(article=article, recent_news=recent_news),
    )


# Legacy paths remain available for old bookmarks and navigation links.
def politika(request):
    return category_page(request, "politika")


def ekonomika(request):
    return category_page(request, "ekonomika")


def obshchestvo(request):
    return category_page(request, "obshchestvo")


def mir(request):
    return category_page(request, "mir")


def tehnologii(request):
    return category_page(request, "tehnologii")


def sport(request):
    return category_page(request, "sport")


def kultura(request):
    return category_page(request, "kultura")
