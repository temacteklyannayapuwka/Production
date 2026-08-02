from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone
from .models import *


def index(request):
    now = timezone.now()
    published_news = (
        News.objects
        .filter(is_published=True, date_start__lte=now)
        .filter(Q(date_end__isnull=True) | Q(date_end__gte=now))
        .select_related('category')
        .order_by('-date_start', '-created_at')
    )

    context = {
        'lead_news': published_news.first(),
        'short_news': published_news[1:6],
        'card_news': published_news[6:10],
        'headline_news': published_news[10:22],
        'popular_news': published_news.order_by('-views', '-date_start')[:5],
        'categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
    }
    return render(request, 'news/index.html', context)

def politika(request):
    context = {}
    return render(request, 'politika.html', context)

def ekonomika(request):
    context = {}
    return render(request, 'ekonomika.html', context)

def obshchestvo(request):
    context = {}
    return render(request, 'obshchestvo.html', context)

def mir(request):
    context = {}
    return render(request, 'mir.html', context)

def tehnologii(request):
    context = {}
    return render(request, 'tehnologii.html', context)

def sport(request):
    context = {}
    return render(request, 'sport.html', context)

def kultura(request):
    context = {}
    return render(request, 'kultura.html', context)
