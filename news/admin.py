from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import *


class NewsGalleryInline(admin.TabularInline):
    model = NewsGallery
    extra = 1
    fields = ('image', 'caption', 'order')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'icon', 'order', 'is_active', 'news_count')
    list_display_links = ('id', 'name')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active')

    def news_count(self, obj):
        return obj.news.count()
    news_count.short_description = 'Новостей'


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title_short',
        'category',
        'photo_preview',
        'is_published',
        'views',
        'date_start',
        'created_at'
    )
    list_display_links = ('id', 'title_short')
    list_filter = (
        'is_published',
        'category',
        'date_start',
        'created_at',
    )
    search_fields = ('title', 'content', 'excerpt', 'meta_keywords')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-date_start', '-created_at')
    list_editable = ('is_published',)
    date_hierarchy = 'date_start'
    readonly_fields = ('views', 'created_at', 'updated_at', 'photo_display')
    inlines = [NewsGalleryInline]

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'title',
                'slug',
                'category',
                'content',
                'excerpt',
            )
        }),
        ('Медиа', {
            'fields': (
                'main_photo',
                'photo_display',
            )
        }),
        ('Публикация', {
            'fields': (
                'is_published',
                'date_start',
                'date_end',
            )
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': (
                'meta_title',
                'meta_description',
                'meta_keywords',
            )
        }),
        ('Статистика', {
            'classes': ('collapse',),
            'fields': (
                'views',
                'created_at',
                'updated_at',
            )
        }),
    )

    def title_short(self, obj):
        if len(obj.title) > 60:
            return obj.title[:60] + '...'
        return obj.title
    title_short.short_description = 'Заголовок'

    def photo_preview(self, obj):
        if obj.main_photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.main_photo.url
            )
        return '—'
    photo_preview.short_description = 'Фото'

    def photo_display(self, obj):
        if obj.main_photo:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px; border-radius: 8px;" />',
                obj.main_photo.url
            )
        return 'Фото не загружено'
    photo_display.short_description = 'Предпросмотр фото'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category')


@admin.register(NewsGallery)
class NewsGalleryAdmin(admin.ModelAdmin):
    list_display = ('id', 'news', 'image_preview', 'caption', 'order')
    list_display_links = ('id', 'news')
    list_filter = ('news',)
    search_fields = ('news__title', 'caption')
    ordering = ('news', 'order')

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return '—'
    image_preview.short_description = 'Превью'


admin.site.site_header = 'Админ-панель StavPlus'
admin.site.site_title = 'StavPlus Admin'
admin.site.index_title = 'Управление новостным порталом'
