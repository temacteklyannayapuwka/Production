from django.urls import path

from . import views


urlpatterns = [
    # ISPmanager's default Nginx template proxies JavaScript to Django while
    # serving the rest of /static/ directly. These narrow fallbacks keep the
    # interfaces usable without changing host-level Nginx configuration.
    path('static/unfold/js/<path:asset_path>', views.serve_unfold_javascript),
    path('static/admin/js/<path:asset_path>', views.serve_admin_javascript),
    path('static/ckeditor/<path:asset_path>', views.serve_ckeditor_javascript),
    path('static/news-site.js', views.serve_public_javascript),
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('tag/<slug:tag_slug>/', views.tag_page, name='tag'),
    path('rubric/<slug:category_slug>/', views.category_page, name='category'),
    # Legacy paths remain available for old bookmarks and navigation links.
    path('politika/', views.politika, name='politika'),
    path('ekonomika/', views.ekonomika, name='ekonomika'),
    path('obshchestvo/', views.obshchestvo, name='obshchestvo'),
    path('mir/', views.mir, name='mir'),
    path('tehnologii/', views.tehnologii, name='tehnologii'),
    path('sport/', views.sport, name='sport'),
    path('kultura/', views.kultura, name='kultura'),
]
