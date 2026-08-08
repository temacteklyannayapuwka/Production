from django.db.models import F, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Category, News


def published_news():
    """News that may be shown publicly at the current moment."""
    now = timezone.now()
    return (
        News.objects.select_related("category")
        .filter(is_published=True, date_start__lte=now)
        .filter(Q(date_end__isnull=True) | Q(date_end__gte=now))
        .order_by("-date_start", "-created_at")
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
            fresh_news=news[1:6],
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
