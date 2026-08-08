"""
StavPlus URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from news import views

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('rubric/<slug:category_slug>/', views.category_page, name='category'),
    path('politika/', views.politika, name='politika'),
    path('ekonomika/', views.ekonomika, name='ekonomika'),
    path('obshchestvo/', views.obshchestvo, name='obshchestvo'),
    path('mir/', views.mir, name='mir'),
    path('tehnologii/', views.tehnologii, name='tehnologii'),
    path('sport/', views.sport, name='sport'),
    path('kultura/', views.kultura, name='kultura'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('admin/', admin.site.urls),
]
