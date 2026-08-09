from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Advertisement, Category, News, NewsGallery


class NewsAdminForm(forms.ModelForm):
    """Present a clear editorial workflow instead of technical field names."""

    class Meta:
        model = News
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        editorial_copy = {
            'title': (
                'Заголовок',
                'Главная фраза новости. Она появится в ленте и в шапке статьи.',
            ),
            'category': (
                'Раздел сайта',
                'Выбери тему, например «Общество» или «Спорт».',
            ),
            'main_photo': (
                'Главное фото',
                'Картинка для карточки новости и шапки статьи. JPG и PNG сайт сам превратит в быструю WebP-версию.',
            ),
            'excerpt': (
                'Короткий анонс',
                'Короткое описание для карточек и поиска. Можно оставить пустым — сайт возьмёт начало основной статьи.',
            ),
            'content': (
                'Основной текст — сюда вписывается вся статья',
                'Здесь находится весь текст новости. Редактор можно развернуть на весь экран кнопкой ⛶; фото в тексте добавляй через кнопку изображения, а подборку фото после статьи — в блоке «Фотогалерея».',
            ),
            'editorial_status': (
                'Статус материала',
                '«Черновик» виден только редакции. «Запланирована» выйдет в указанное время. «На сайте» публикуется сразу.',
            ),
            'is_featured': (
                'Главная новость',
                'Включи, чтобы поставить этот материал в большой блок на главной странице. Предыдущая главная новость сменится автоматически.',
            ),
            'date_start': (
                'Показать на сайте с',
                'Оставь текущее время для публикации сейчас или выбери дату для отложенной публикации.',
            ),
            'date_end': (
                'Снять с публикации',
                'Необязательно. Укажи дату, если новость должна исчезнуть с сайта автоматически.',
            ),
            'slug': (
                'Адрес страницы',
                'Создаётся автоматически из заголовка. Меняй только если нужен особый короткий адрес.',
            ),
            'meta_title': (
                'Заголовок для поисковиков',
                'Необязательно. Если оставить пустым, будет использован обычный заголовок.',
            ),
            'meta_description': (
                'Описание для поисковиков',
                'Необязательно. Это текст под ссылкой в выдаче Google и Яндекса.',
            ),
            'meta_keywords': (
                'Ключевые слова',
                'Необязательно. Перечисли слова через запятую.',
            ),
        }
        for name, (label, help_text) in editorial_copy.items():
            if name in self.fields:
                self.fields[name].label = label
                self.fields[name].help_text = help_text

        self.fields['main_photo'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        self.fields['excerpt'].widget.attrs.update({
            'rows': 4,
            'style': 'width: 100%; max-width: none;',
        })

        # New items start as drafts. Existing news retain their saved state.
        if not self.instance.pk:
            self.fields['editorial_status'].initial = News.EditorialStatus.DRAFT


class NewsGalleryInlineForm(forms.ModelForm):
    class Meta:
        model = NewsGallery
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].help_text = 'JPG и PNG автоматически станут WebP.'
        self.fields['caption'].help_text = 'Подпись под фотографией — необязательно.'
        self.fields['order'].help_text = 'Меньшее число покажет фото раньше.'


class NewsGalleryInline(admin.StackedInline):
    model = NewsGallery
    form = NewsGalleryInlineForm
    extra = 1
    fields = ('image', 'caption', 'order')
    verbose_name = 'Фото для галереи'
    verbose_name_plural = '4. Фотогалерея материала'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active', 'news_count')
    list_display_links = ('name',)
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active')
    fieldsets = (
        ('Раздел сайта', {
            'description': 'Название увидят читатели в меню и на странице раздела.',
            'fields': ('name', 'description', 'icon'),
        }),
        ('Порядок и отображение', {
            'description': 'Меньшее число показывает раздел выше в меню. Отключённый раздел не виден читателям.',
            'fields': ('order', 'is_active'),
        }),
        ('Технические настройки', {
            'classes': ('collapse',),
            'fields': ('slug',),
        }),
    )

    @admin.display(description='Новостей')
    def news_count(self, obj):
        return obj.news.count()


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    form = NewsAdminForm
    change_form_template = 'admin/news/news/change_form.html'
    change_list_template = 'admin/news/news/change_list.html'
    list_display = (
        'title_short',
        'category',
        'editorial_status',
        'is_featured',
        'date_start',
        'photo_preview',
        'updated_at',
    )
    list_display_links = ('title_short',)
    list_editable = ('editorial_status', 'is_featured')
    list_filter = ('editorial_status', 'is_featured', 'category', 'date_start', 'created_at')
    search_fields = ('title', 'content', 'excerpt', 'meta_keywords')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-date_start', '-created_at')
    date_hierarchy = 'date_start'
    list_per_page = 25
    list_before_template = 'admin/news/news/news_list_actions.html'
    readonly_fields = ('views', 'created_at', 'updated_at', 'photo_display')
    inlines = [NewsGalleryInline]
    actions = (
        'make_selected_featured',
        'clear_selected_featured',
        'publish_selected',
        'unpublish_selected',
    )
    save_on_top = True

    @admin.display(description='Новость')
    def title_short(self, obj):
        return f'{obj.title[:60]}…' if len(obj.title) > 60 else obj.title

    @admin.display(description='Фото')
    def photo_preview(self, obj):
        if obj.main_photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 8px;" alt="" />',
                obj.main_photo.url,
            )
        return '—'

    @admin.display(description='Предпросмотр главного фото')
    def photo_display(self, obj):
        if obj.main_photo:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px; border-radius: 8px;" alt="Предпросмотр главного фото" />',
                obj.main_photo.url,
            )
        return 'Загрузи главное фото и сохрани новость — здесь появится предпросмотр.'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')

    def get_fieldsets(self, request, obj=None):
        card_fields = ['title', 'category', 'main_photo']
        if obj and obj.main_photo:
            card_fields.append('photo_display')

        return (
            ('1. Основа новости', {
                'description': 'Заполни заголовок, раздел и главное фото. Это читатель увидит в ленте.',
                'fields': tuple(card_fields),
            }),
            ('2. Текст материала', {
                'description': 'Сначала впиши всю статью в большой редактор. Ниже добавь короткий анонс для карточек или оставь его пустым — сайт составит анонс сам.',
                'fields': ('content', 'excerpt'),
            }),
            ('3. Публикация', {
                'description': 'Выбери статус, отметь главную новость при необходимости и задай время. Главной может быть только одна новость — новая отметка заменит прежнюю.',
                'fields': ('editorial_status', 'is_featured', 'date_start', 'date_end'),
            }),
            ('Настройки страницы', {
                'classes': ('collapse',),
                'description': 'Обычно эти настройки не нужны: адрес и данные для поисковиков создаются автоматически.',
                'fields': ('slug', 'meta_title', 'meta_description', 'meta_keywords'),
            }),
            ('Служебная информация', {
                'classes': ('collapse',),
                'fields': ('views', 'created_at', 'updated_at'),
            }),
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['editorial_can_add'] = request.user.has_perm('news.add_news')
        extra_context['editorial_add_url'] = reverse('admin:news_news_add')
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Опубликовать выбранные новости')
    def publish_selected(self, request, queryset):
        queryset.update(
            editorial_status=News.EditorialStatus.PUBLISHED,
            is_published=True,
            date_start=timezone.now(),
        )
        self.message_user(request, 'Выбранные новости опубликованы.')

    @admin.action(description='Сделать выбранную новость главной')
    def make_selected_featured(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                'Выбери одну новость — она появится в большом блоке на главной странице.',
                level=messages.ERROR,
            )
            return

        news = queryset.first()
        news.is_featured = True
        news.save(update_fields=('is_featured',))
        self.message_user(request, f'Главная новость: «{news.title}».')

    @admin.action(description='Убрать выбранные новости с главного места')
    def clear_selected_featured(self, request, queryset):
        changed = queryset.filter(is_featured=True).update(is_featured=False)
        if changed:
            self.message_user(request, 'Выбранные новости больше не закреплены на главной.')
        else:
            self.message_user(request, 'Среди выбранных новостей нет главной.', level=messages.INFO)

    @admin.action(description='Снять выбранные новости с публикации')
    def unpublish_selected(self, request, queryset):
        queryset.update(
            editorial_status=News.EditorialStatus.DRAFT,
            is_published=False,
        )
        self.message_user(request, 'Выбранные новости переведены в черновики.')


@admin.register(NewsGallery)
class NewsGalleryAdmin(admin.ModelAdmin):
    list_display = ('news', 'image_preview', 'caption', 'order')
    list_display_links = ('news',)
    list_filter = ('news',)
    search_fields = ('news__title', 'caption')
    ordering = ('news', 'order')

    @admin.display(description='Фото')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit: cover; border-radius: 8px;" alt="" />',
                obj.image.url,
            )
        return '—'


class AdvertisementAdminForm(forms.ModelForm):
    """A concise banner workflow for editors rather than technical ad settings."""

    class Meta:
        model = Advertisement
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        copy = {
            'name': ('Название баннера', 'Внутреннее название для редакции — читатели его не увидят.'),
            'placement': ('Где показывать', 'Каждое место на сайте может занимать один баннер. Чтобы заменить рекламу, открой существующий баннер этого места.'),
            'image': ('Файл баннера', 'Загрузи JPG, PNG или WebP. JPG и PNG автоматически конвертируются в WebP для быстрой загрузки.'),
            'link': ('Ссылка при клике', 'Необязательно. Если оставить пустым, баннер будет только изображением.'),
            'alt_text': ('Короткое описание', 'Текст для доступности и поисковых систем. Например: «Летний фестиваль в Ставрополе». '),
            'is_enabled': ('Показывать баннер', 'Выключи, чтобы временно скрыть баннер без удаления файла.'),
            'date_start': ('Показывать с', 'Дата и время начала показа.'),
            'date_end': ('Снять с показа', 'Необязательно. После этой даты баннер скроется сам.'),
        }
        for name, (label, help_text) in copy.items():
            if name in self.fields:
                self.fields[name].label = label
                self.fields[name].help_text = help_text
        self.fields['image'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    form = AdvertisementAdminForm
    change_form_template = 'admin/news/advertisement/change_form.html'
    change_list_template = 'admin/news/advertisement/change_list.html'
    list_display = ('name', 'placement', 'is_enabled', 'date_start', 'date_end', 'banner_preview')
    list_display_links = ('name',)
    list_editable = ('is_enabled',)
    list_filter = ('placement', 'is_enabled', 'date_start')
    search_fields = ('name', 'alt_text', 'link')
    ordering = ('placement', 'name')
    list_per_page = 25
    readonly_fields = ('banner_preview', 'updated_at')
    save_on_top = True

    fieldsets = (
        ('1. Место и файл', {
            'description': 'Сначала выбери место на сайте, затем загрузи изображение. Размер баннера указан прямо в списке мест.',
            'fields': ('name', 'placement', 'image', 'banner_preview'),
        }),
        ('2. Переход и подпись', {
            'description': 'Ссылка и описание не обязательны, но помогают читателю понять рекламу.',
            'fields': ('link', 'open_in_new_tab', 'alt_text'),
        }),
        ('3. Показ', {
            'description': 'Отключи баннер или задай даты, чтобы управлять размещением без удаления.',
            'fields': ('is_enabled', 'date_start', 'date_end'),
        }),
        ('Служебная информация', {'classes': ('collapse',), 'fields': ('updated_at',)}),
    )

    @admin.display(description='Предпросмотр')
    def banner_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="max-width: 420px; max-height: 180px; border-radius: 8px; object-fit: cover;" alt="Предпросмотр баннера" />',
                obj.image.url,
            )
        return 'Загрузи файл и сохрани баннер — здесь появится предпросмотр.'


admin.site.site_header = 'Ставрополь+ · редакция'
admin.site.site_title = 'Ставрополь+ · редакция'
admin.site.index_title = 'Редакционная панель'
