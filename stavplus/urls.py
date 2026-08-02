"""
StavPlus URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from news.views import *

urlpatterns = [
    path('', index, name='index'),
    path('politika/', politika, name='politika'),
    path('ekonomika/', ekonomika, name='ekonomika'),
    path('obshchestvo/', obshchestvo, name='obshchestvo'),
    path('mir/', mir, name='mir'),
    path('tehnologii/', tehnologii, name='tehnologii'),
    path('sport/', sport, name='sport'),
    path('kultura/', kultura, name='kultura'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('admin/', admin.site.urls),
]
