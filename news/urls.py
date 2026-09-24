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
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.public_sitemap, name='sitemap'),
    path('news-sitemap.xml', views.google_news_sitemap, name='news_sitemap'),
    path('index.html', views.index_file_redirect, name='legacy_index_html'),
    path('index.php', views.index_file_redirect, name='legacy_index_php'),
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('tag/<slug:tag_slug>/', views.tag_page, name='tag'),
    path('rubric/<slug:category_slug>/', views.category_page, name='category'),
    # Legacy paths remain available for old bookmarks and navigation links.
    path(
        'politika/',
        views.legacy_category_redirect,
        {'category_slug': 'politika'},
        name='politika',
    ),
    path(
        'ekonomika/',
        views.legacy_category_redirect,
        {'category_slug': 'ekonomika'},
        name='ekonomika',
    ),
    path(
        'obshchestvo/',
        views.legacy_category_redirect,
        {'category_slug': 'obshchestvo'},
        name='obshchestvo',
    ),
    path(
        'mir/',
        views.legacy_category_redirect,
        {'category_slug': 'mir'},
        name='mir',
    ),
    path(
        'tehnologii/',
        views.legacy_category_redirect,
        {'category_slug': 'tehnologii'},
        name='tehnologii',
    ),
    path(
        'sport/',
        views.legacy_category_redirect,
        {'category_slug': 'sport'},
        name='sport',
    ),
    path(
        'kultura/',
        views.legacy_category_redirect,
        {'category_slug': 'kultura'},
        name='kultura',
    ),
]
