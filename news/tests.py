from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, News


class HomePageTests(TestCase):
    def test_homepage_uses_the_new_design_when_the_database_is_empty(self):
        response = self.client.get(reverse('index'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'news/index.html')
        self.assertContains(response, 'home.css')
        self.assertContains(response, 'MAX')
        self.assertNotContains(response, 'style-new.css')

    def test_homepage_shows_only_currently_published_news(self):
        category = Category.objects.create(name='Общество', slug='obshchestvo')
        visible_news = News.objects.create(
            title='Опубликованная новость',
            content='Содержание опубликованной новости.',
            category=category,
            is_published=True,
            date_start=timezone.now(),
        )
        News.objects.create(
            title='Черновик',
            content='Эта новость не должна появиться на главной.',
            category=category,
            is_published=False,
            date_start=timezone.now(),
        )

        response = self.client.get(reverse('index'))

        self.assertContains(response, visible_news.title)
        self.assertNotContains(response, 'Черновик')
