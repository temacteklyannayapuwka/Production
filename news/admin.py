from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from unfold.admin import ModelAdmin, StackedInline

from .ai_news.publication import PublicationPolicyError, publish_ai_draft
from .models import (
    AIRewriteAuditEvent,
    Advertisement,
    Category,
    ImportedNewsItem,
    News,
    NewsGallery,
    NewsSource,
    Tag,
)


class CategoryAdminForm(forms.ModelForm):
    """Keep section editing focused on labels readers actually see."""

    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].label = 'Описание раздела'
        self.fields['description'].help_text = (
            'Текст страницы раздела. Поле можно растянуть по высоте за нижний правый угол.'
        )
        self.fields['description'].widget.attrs.update({
            'rows': 12,
            'class': 'editorial-description-field',
        })
        self.fields['order'].label = 'Позиция в меню'
        self.fields['order'].help_text = 'Меньшее число показывает раздел выше.'
        self.fields['is_active'].label = 'Показывать раздел на сайте'
        self.fields['is_active'].help_text = (
            'Выключи, чтобы скрыть раздел от читателей без удаления.'
        )


class NewsAdminForm(forms.ModelForm):
    """Present a clear editorial workflow instead of technical field names."""

    content = forms.CharField(
        label='Основной текст',
        widget=CKEditorUploadingWidget(
            config_name='default',
            attrs={
                'style': 'width: 100%; max-width: none; resize: both;',
            },
        ),
    )

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
            'tags': (
                'Теги темы',
                'Выбери от 1 до 5 уточняющих тем: например «Транспорт», «Ставрополь», «Благоустройство». Новые теги создаются в разделе «Теги» слева.',
            ),
            'main_photo': (
                'Главное изображение',
                'Изображение для карточки и страницы статьи. Оно заполняет ширину блока; JPG и PNG при новой загрузке преобразуются в WebP.',
            ),
            'excerpt': (
                'Лид — краткое вступление',
                'Показывается между заголовком и изображением, а также в карточках. Не повторяй этот абзац в основном тексте.',
            ),
            'content': (
                'Основной текст',
                'Продолжение материала без повтора лида. Поле растягивается за нижний правый угол по ширине и высоте; редактор можно развернуть на весь экран кнопкой ⛶.',
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
        self.fields['title'].widget.attrs.update({
            'style': 'width: 100%; max-width: none;',
        })
        self.fields['excerpt'].widget.attrs.update({
            'rows': 4,
            'style': 'width: 100%; max-width: none;',
        })

        # New items start as drafts. Existing news retain their saved state.
        if not self.instance.pk:
            self.fields['editorial_status'].initial = News.EditorialStatus.DRAFT

    def clean(self):
        cleaned_data = super().clean()
        requested_status = cleaned_data.get('editorial_status')
        if (
            self.instance.pk
            and self.initial.get('editorial_status') == News.EditorialStatus.DRAFT
            and requested_status != News.EditorialStatus.DRAFT
            and ImportedNewsItem.objects.filter(created_news_id=self.instance.pk).exists()
        ):
            raise forms.ValidationError(
                'AI-черновик публикуется только явным действием «Опубликовать» в админке.'
            )
        return cleaned_data


class NewsGalleryInlineForm(forms.ModelForm):
    class Meta:
        model = NewsGallery
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].help_text = 'JPG и PNG автоматически станут WebP.'
        self.fields['caption'].help_text = 'Подпись под фотографией — необязательно.'
        self.fields['order'].help_text = 'Меньшее число покажет фото раньше.'


class NewsGalleryInline(StackedInline):
    model = NewsGallery
    form = NewsGalleryInlineForm
    extra = 2
    fields = ('image', 'caption', 'order')
    verbose_name = 'Фотография карусели'
    verbose_name_plural = '4. Фотокарусель'


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'order', 'is_active', 'news_count')
    list_display_links = ('name',)
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    list_editable = ('order', 'is_active')
    list_filter_sheet = True
    fieldsets = (
        ('Раздел сайта', {
            'description': 'Название увидят читатели в меню и на странице раздела.',
            'fields': ('name', 'description'),
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

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(news_total=Count('news'))

    @admin.display(description='Новостей', ordering='news_total')
    def news_count(self, obj):
        return obj.news_total


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'news_count')
    list_display_links = ('name',)
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    list_filter_sheet = True
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)
    fieldsets = (
        ('Тег', {
            'description': 'Тег — дополнительная тема новости. Например: «Транспорт», «Семья», «Городская среда». Один тег можно использовать в разных разделах.',
            'fields': ('name', 'description'),
        }),
        ('Показ на сайте', {
            'description': 'Включённый тег появляется в статьях и открывает страницу со всеми материалами по этой теме.',
            'fields': ('is_active',),
        }),
        ('Технические настройки', {
            'classes': ('collapse',),
            'fields': ('slug',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(news_total=Count('news_items'))

    @admin.display(description='Новостей', ordering='news_total')
    def news_count(self, obj):
        return obj.news_total


@admin.register(News)
class NewsAdmin(ModelAdmin):
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
    list_filter_sheet = True
    search_fields = ('title', 'content', 'excerpt', 'meta_keywords', 'tags__name')
    autocomplete_fields = ('tags',)
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-date_start', '-created_at')
    date_hierarchy = 'date_start'
    list_per_page = 25
    list_before_template = 'admin/news/news/news_list_actions.html'
    readonly_fields = (
        'views',
        'created_at',
        'updated_at',
        'photo_display',
        'import_source',
    )
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

    @admin.display(description='Источник материала')
    def import_source(self, obj):
        ai_import = getattr(obj, 'ai_import', None) if obj else None
        if ai_import:
            return format_html(
                'AI-рерайт · <a href="{}">{}</a>',
                reverse('admin:news_importednewsitem_change', args=(ai_import.pk,)),
                ai_import.source_name,
            )
        if obj and obj.legacy_k2_id:
            return f'Архив Joomla K2 · ID {obj.legacy_k2_id}'
        return 'Создано в редакции StavPlus'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')

    def get_fieldsets(self, request, obj=None):
        card_fields = ['title', 'category', 'tags', 'main_photo']
        if obj and obj.main_photo:
            card_fields.append('photo_display')

        return (
            ('1. Основа новости', {
                'description': 'Заполни заголовок, раздел, теги и главное фото. Это читатель увидит в ленте и на странице статьи.',
                'fields': tuple(card_fields),
            }),
            ('2. Текст материала', {
                'description': 'Лид и основной текст — разные части статьи. Лид показывается отдельно, поэтому не нужно повторять его в редакторе основного текста.',
                'fields': ('excerpt', 'content'),
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
                'fields': ('import_source', 'views', 'created_at', 'updated_at'),
            }),
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['editorial_can_add'] = request.user.has_perm('news.add_news')
        extra_context['editorial_add_url'] = reverse('admin:news_news_add')
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Опубликовать выбранные новости')
    def publish_selected(self, request, queryset):
        actor = request.user.get_username()
        regular_ids = []
        published_ai = 0
        skipped_ai = 0
        for news in queryset.select_related('ai_import'):
            try:
                item = news.ai_import
            except ImportedNewsItem.DoesNotExist:
                regular_ids.append(news.pk)
                continue
            try:
                publish_ai_draft(item.pk, actor=actor)
            except PublicationPolicyError:
                skipped_ai += 1
            else:
                published_ai += 1
        published_regular = News.objects.filter(pk__in=regular_ids).update(
            editorial_status=News.EditorialStatus.PUBLISHED,
            is_published=True,
            date_start=timezone.now(),
        )
        self.message_user(
            request,
            f'Опубликовано: {published_regular + published_ai}.',
        )
        if skipped_ai:
            self.message_user(
                request,
                f'AI-черновиков пропущено политикой публикации: {skipped_ai}.',
                level=messages.WARNING,
            )

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


@admin.register(NewsSource)
class NewsSourceAdmin(ModelAdmin):
    list_display = (
        'name',
        'source_type',
        'is_active',
        'editorial_approved',
        'legal_approved',
        'approval_state',
        'last_fetched_at',
    )
    list_filter = ('source_type', 'is_active', 'editorial_approved', 'legal_approved')
    search_fields = ('name', 'website_url', 'feed_url', 'allowed_domains')
    readonly_fields = ('last_fetched_at', 'created_at', 'updated_at')
    list_filter_sheet = True
    fieldsets = (
        ('Источник', {
            'fields': ('name', 'website_url', 'feed_url', 'source_type', 'allowed_domains'),
        }),
        ('Разрешения', {
            'description': (
                'Загрузка начнётся только после редакционного и юридического согласования, '
                'а также документированной проверки robots.txt и условий использования.'
            ),
            'fields': (
                'is_active',
                'editorial_approved',
                'legal_approved',
                'terms_url',
                'terms_reviewed_at',
                'robots_reviewed_at',
            ),
        }),
        ('Ограничения запросов', {
            'fields': ('min_request_interval_minutes', 'last_fetched_at'),
        }),
        ('Примечания', {'fields': ('notes', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Готов к загрузке', boolean=True)
    def approval_state(self, obj):
        return obj.is_approved_for_ingestion


class AIRewriteAuditEventInline(admin.TabularInline):
    model = AIRewriteAuditEvent
    extra = 0
    can_delete = False
    fields = ('created_at', 'event_type', 'actor', 'message')
    readonly_fields = fields
    ordering = ('-created_at', '-pk')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImportedNewsItem)
class ImportedNewsItemAdmin(ModelAdmin):
    list_display = (
        'source_title_short',
        'source',
        'status',
        'rewrite_model',
        'fetched_at',
        'created_draft_link',
    )
    list_filter = ('status', 'source', 'rewrite_model', 'fetched_at')
    search_fields = ('source_title', 'source_url', 'source_name', 'content_hash', 'error_message')
    list_filter_sheet = True
    readonly_fields = (
        'source',
        'source_url_link',
        'source_name',
        'source_title',
        'source_published_at',
        'fetched_at',
        'normalized_text',
        'content_hash',
        'extracted_facts',
        'status',
        'rewrite_model',
        'prompt_version',
        'provider_response_id',
        'source_facts',
        'warnings',
        'error_message',
        'retry_count',
        'input_tokens',
        'output_tokens',
        'provider_cost_usd',
        'created_draft_link',
        'last_attempted_at',
        'created_at',
        'updated_at',
    )
    fields = readonly_fields
    inlines = (AIRewriteAuditEventInline,)
    actions = ('retry_rewrite', 'publish_created_draft')
    ordering = ('-fetched_at', '-pk')

    @admin.display(description='Материал')
    def source_title_short(self, obj):
        return f'{obj.source_title[:70]}…' if len(obj.source_title) > 70 else obj.source_title

    @admin.display(description='Оригинальный URL')
    def source_url_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            obj.source_url,
            obj.source_url,
        )

    @admin.display(description='Созданный черновик')
    def created_draft_link(self, obj):
        if not obj.created_news_id:
            return '—'
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:news_news_change', args=(obj.created_news_id,)),
            obj.created_news.title,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('source', 'created_news')

    @admin.action(description='Повторить AI-рерайт')
    def retry_rewrite(self, request, queryset):
        eligible = queryset.exclude(
            status__in=(
                ImportedNewsItem.ProcessingStatus.PROCESSING,
                ImportedNewsItem.ProcessingStatus.PUBLISHED,
            )
        )
        count = 0
        for item in eligible:
            item.status = ImportedNewsItem.ProcessingStatus.PENDING
            item.error_message = ''
            item.save(update_fields=('status', 'error_message', 'updated_at'))
            AIRewriteAuditEvent.objects.create(
                item=item,
                event_type='retry_requested',
                actor=request.user.get_username(),
                message='Редактор запросил повторный AI-рерайт.',
            )
            count += 1
        self.message_user(request, f'На повторный рерайт отправлено: {count}.')

    @admin.action(description='Отправить созданный черновик в публикацию')
    def publish_created_draft(self, request, queryset):
        published = 0
        skipped = 0
        for item in queryset:
            try:
                publish_ai_draft(item.pk, actor=request.user.get_username())
            except PublicationPolicyError:
                skipped += 1
            else:
                published += 1
        if published:
            self.message_user(request, f'Опубликовано вручную: {published}.')
        if skipped:
            self.message_user(
                request,
                f'Пропущено из-за отсутствующего черновика или обязательных полей: {skipped}.',
                level=messages.WARNING,
            )


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
class AdvertisementAdmin(ModelAdmin):
    form = AdvertisementAdminForm
    change_form_template = 'admin/news/advertisement/change_form.html'
    change_list_template = 'admin/news/advertisement/change_list.html'
    list_display = ('name', 'placement', 'is_enabled', 'date_start', 'date_end', 'banner_preview')
    list_display_links = ('name',)
    list_editable = ('is_enabled',)
    list_filter = ('placement', 'is_enabled', 'date_start')
    list_filter_sheet = True
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
