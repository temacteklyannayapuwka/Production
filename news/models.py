from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from transliterate import translit
from ckeditor_uploader.fields import RichTextUploadingField

from .image_processing import convert_pending_upload_to_webp


class Category(models.Model):
    name = models.CharField('Название', max_length=100, unique=True)
    slug = models.SlugField('URL', unique=True, max_length=100)
    description = models.TextField('Описание', blank=True)
    icon = models.CharField('Иконка', max_length=50, blank=True)
    order = models.IntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    """A reusable, editor-managed topic label for one or more news items."""

    name = models.CharField('Название тега', max_length=80, unique=True)
    slug = models.SlugField('URL', unique=True, max_length=100, blank=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField(
        'Показывать на сайте',
        default=True,
        help_text='Выключи, чтобы временно скрыть тег и его страницу от читателей.',
    )

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            try:
                base_slug = slugify(translit(self.name, 'ru', reversed=True))
            except Exception:
                base_slug = slugify(self.name)
            base_slug = base_slug or 'tag'
            candidate = base_slug
            suffix = 2
            while type(self).objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f'{base_slug}-{suffix}'
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class News(models.Model):
    class EditorialStatus(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        SCHEDULED = 'scheduled', 'Запланирована'
        PUBLISHED = 'published', 'На сайте'

    title = models.CharField('Заголовок', max_length=255)
    slug = models.SlugField('URL', unique=True, max_length=255, blank=True)
    content = RichTextUploadingField('Содержание')
    excerpt = models.TextField('Краткое описание', max_length=500, blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news',
        verbose_name='Категория'
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='news_items',
        verbose_name='Теги',
        help_text='Добавь от 1 до 5 меток, по которым читатель сможет найти похожие материалы.',
    )

    main_photo = models.ImageField(
        'Главное фото',
        upload_to='news/main/%Y/%m/',
        blank=True,
        null=True
    )

    is_published = models.BooleanField('Опубликовано', default=True, db_index=True)
    editorial_status = models.CharField(
        'Статус',
        max_length=12,
        choices=EditorialStatus.choices,
        default=EditorialStatus.DRAFT,
        db_index=True,
        help_text='Черновик не виден читателям. Запланированная новость выйдет в указанное время.',
    )
    is_featured = models.BooleanField(
        'Главная новость',
        default=False,
        db_index=True,
        help_text='Показывать этот материал в большом блоке на главной странице.',
    )
    date_start = models.DateTimeField('Дата начала публикации', default=timezone.now, db_index=True)
    date_end = models.DateTimeField('Дата окончания публикации', null=True, blank=True)

    meta_title = models.CharField('SEO заголовок', max_length=255, blank=True)
    meta_description = models.TextField('SEO описание', max_length=255, blank=True)
    meta_keywords = models.CharField('Ключевые слова', max_length=255, blank=True)

    views = models.IntegerField('Просмотры', default=0, editable=False)

    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
        ordering = ['-date_start']
        indexes = [
            models.Index(fields=['-date_start', 'is_published']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.editorial_status == self.EditorialStatus.DRAFT:
            self.is_published = False
        elif self.editorial_status == self.EditorialStatus.SCHEDULED:
            self.is_published = True
            if self.date_start <= now:
                self.date_start = now + timedelta(hours=1)
        else:
            self.is_published = True
            if self.date_start > now:
                self.date_start = now

        converted_image = convert_pending_upload_to_webp(self.main_photo)
        if converted_image:
            self.main_photo.save(*converted_image, save=False)

        if not self.slug:
            try:
                transliterated = translit(self.title, 'ru', reversed=True)
                self.slug = slugify(transliterated)
            except:
                self.slug = slugify(self.title)

        if not self.excerpt and self.content:
            import re
            clean_content = re.sub('<[^<]+?>', '', self.content)
            self.excerpt = clean_content[:200].strip() + ('...' if len(clean_content) > 200 else '')

        if not self.meta_title:
            self.meta_title = self.title
        if not self.meta_description:
            self.meta_description = self.excerpt

        if self.is_featured:
            # The homepage has one lead material. Selecting a new one replaces
            # the old choice while retaining all of its publication data.
            with transaction.atomic():
                type(self).objects.filter(is_featured=True).exclude(pk=self.pk).update(
                    is_featured=False
                )
                super().save(*args, **kwargs)
            return

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('news_detail', kwargs={'slug': self.slug})

    @property
    def is_active(self):
        now = timezone.now()
        if not self.is_published:
            return False
        if self.date_start > now:
            return False
        if self.date_end and self.date_end < now:
            return False
        return True


class NewsGallery(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='gallery', verbose_name='Новость')
    image = models.ImageField('Изображение', upload_to='news/gallery/%Y/%m/')
    caption = models.CharField('Подпись', max_length=255, blank=True)
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото галереи'
        verbose_name_plural = 'Фото галереи'
        ordering = ['order']

    def __str__(self):
        return f'{self.news.title} - Фото {self.order}'

    def save(self, *args, **kwargs):
        converted_image = convert_pending_upload_to_webp(self.image)
        if converted_image:
            self.image.save(*converted_image, save=False)
        super().save(*args, **kwargs)


class Advertisement(models.Model):
    class Placement(models.TextChoices):
        TOP = 'top', 'Верх сайта · 970 × 90'
        HOME_SIDEBAR = 'home_sidebar', 'Главная · справа · 300 × 250'
        HOME_BOTTOM = 'home_bottom', 'Главная · нижний баннер · 970 × 90'
        HOME_POPULAR = 'home_popular', 'Главная · «Читают сейчас» · 300 × 600'
        SECTION_SIDEBAR = 'section_sidebar', 'Разделы · справа · 300 × 250'
        SECTION_RAIL = 'section_rail', 'Разделы · нижний правый · 300 × 300'
        SECTION_BOTTOM = 'section_bottom', 'Разделы · нижний баннер · 970 × 90'
        ARTICLE_SIDEBAR = 'article_sidebar', 'Статья · слева · 240 × 400'
        ARTICLE_INLINE = 'article_inline', 'Статья · внутри текста · 680 × 120'

    name = models.CharField('Название баннера', max_length=120)
    placement = models.CharField(
        'Место на сайте',
        max_length=32,
        choices=Placement.choices,
        unique=True,
    )
    image = models.ImageField('Изображение баннера', upload_to='advertising/%Y/%m/')
    link = models.URLField('Ссылка при клике', blank=True)
    alt_text = models.CharField('Описание баннера', max_length=200, blank=True)
    open_in_new_tab = models.BooleanField('Открывать ссылку в новой вкладке', default=True)
    is_enabled = models.BooleanField('Показывать баннер', default=True, db_index=True)
    date_start = models.DateTimeField('Показывать с', default=timezone.now, db_index=True)
    date_end = models.DateTimeField('Снять с показа', blank=True, null=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Рекламный баннер'
        verbose_name_plural = 'Рекламные баннеры'
        ordering = ['placement', 'name']

    def __str__(self):
        return f'{self.get_placement_display()} · {self.name}'

    @property
    def is_active_now(self):
        now = timezone.now()
        return (
            self.is_enabled
            and self.date_start <= now
            and (self.date_end is None or self.date_end >= now)
        )

    def save(self, *args, **kwargs):
        converted_image = convert_pending_upload_to_webp(self.image)
        if converted_image:
            self.image.save(*converted_image, save=False)
        super().save(*args, **kwargs)
