from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from transliterate import translit
from ckeditor.fields import RichTextField


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


class News(models.Model):
    title = models.CharField('Заголовок', max_length=255)
    slug = models.SlugField('URL', unique=True, max_length=255, blank=True)
    content = RichTextField('Содержание')
    excerpt = models.TextField('Краткое описание', max_length=500, blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news',
        verbose_name='Категория'
    )

    main_photo = models.ImageField(
        'Главное фото',
        upload_to='news/main/%Y/%m/',
        blank=True,
        null=True
    )

    is_published = models.BooleanField('Опубликовано', default=True, db_index=True)
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

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('news_detail', kwargs={'pk': self.pk, 'slug': self.slug})

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
