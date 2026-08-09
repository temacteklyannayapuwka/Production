from datetime import timedelta

from django.contrib import admin
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .admin import NewsAdmin, NewsAdminForm
from .models import Category, News
from .views import published_news


class AdminJavascriptFallbackTests(SimpleTestCase):
    def test_public_site_script_is_available_through_django(self):
        response = self.client.get('/static/news-site.js')

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response['Content-Type'])
        self.assertIn(b'data-menu-trigger', b''.join(response.streaming_content))

    def test_public_page_uses_the_current_menu_script(self):
        response = get_template('base.html').render({})

        self.assertIn('/static/news-site.css?v=16', response)
        self.assertIn('/static/brand/stavplus-mark.svg', response)
        self.assertIn('/static/news-site.js?v=2', response)
        self.assertIn('>Меню</span>', response)
        self.assertNotIn('class="header-nav"', response)

    def test_unfold_script_is_available_through_django(self):
        response = self.client.get('/static/unfold/js/app.js')

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response['Content-Type'])

    def test_path_traversal_is_rejected(self):
        response = self.client.get('/static/unfold/js/../../settings.py')

        self.assertEqual(response.status_code, 404)

    def test_admin_loads_the_symbol_font_fix(self):
        response = self.client.get('/admin/login/')

        self.assertContains(response, '/static/admin-symbols.css')
        self.assertContains(response, '/static/admin-editorial.css')
        self.assertContains(response, '--color-primary-600: rgb(71, 85, 105)')


class EditorialAdminTests(SimpleTestCase):
    def test_new_news_form_starts_as_a_draft_with_editorial_help(self):
        form = NewsAdminForm()

        self.assertFalse(form.fields['is_published'].initial)
        self.assertEqual(form.fields['main_photo'].label, 'Главное фото')
        self.assertIn('WebP', form.fields['main_photo'].help_text)
        self.assertIn('Основной текст', form.fields['content'].help_text)
        self.assertEqual(form.fields['is_featured'].label, 'Главная новость')

    def test_add_form_excludes_the_empty_photo_preview(self):
        model_admin = NewsAdmin(News, admin.site)
        fieldsets = model_admin.get_fieldsets(request=None, obj=None)
        first_fields = fieldsets[0][1]['fields']

        self.assertNotIn('photo_display', first_fields)

    def test_editorial_templates_compile(self):
        self.assertIsNotNone(get_template('admin/news/news/change_form.html'))
        self.assertIsNotNone(get_template('admin/news/news/change_list.html'))
        self.assertIsNotNone(get_template('index.html'))

    def test_homepage_omits_the_digest_and_middle_advertisement(self):
        source = get_template('index.html').template.source

        self.assertNotIn('Вечерний дайджест', source)
        self.assertNotIn('ad--wide', source)
        self.assertIn('hero__lead', source)
        self.assertIn('popular__surface', source)
        self.assertIn('Погода · Ставрополь', source)


class FeaturedNewsTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Общество', slug='obshchestvo')

    def create_news(self, slug, *, is_featured=False, date_start=None):
        return News.objects.create(
            title=f'Новость {slug}',
            slug=slug,
            content='<p>Текст новости</p>',
            category=self.category,
            is_published=True,
            is_featured=is_featured,
            date_start=date_start or timezone.now(),
        )

    def test_selecting_a_new_featured_news_replaces_the_old_one(self):
        previous = self.create_news('previous', is_featured=True)
        selected = self.create_news('selected', is_featured=True)

        previous.refresh_from_db()
        self.assertFalse(previous.is_featured)
        self.assertTrue(selected.is_featured)

    def test_featured_news_is_shown_first_on_the_homepage(self):
        recent = self.create_news('recent', date_start=timezone.now())
        featured = self.create_news(
            'featured',
            is_featured=True,
            date_start=timezone.now() - timedelta(days=1),
        )

        self.assertEqual(published_news().first(), featured)
        self.assertNotEqual(published_news().first(), recent)

    def test_featured_status_renders_in_the_admin_list(self):
        featured = self.create_news('admin-featured', is_featured=True)
        model_admin = NewsAdmin(News, admin.site)

        self.assertIn('★ Главная', str(model_admin.featured_status(featured)))

    def test_homepage_feed_contains_every_news_after_lead_and_cards(self):
        for number in range(18):
            self.create_news(
                f'feed-{number}',
                date_start=timezone.now() - timedelta(minutes=number),
            )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['card_news']), 4)
        self.assertEqual(len(response.context['headline_news']), 13)
