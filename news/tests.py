from django.contrib import admin
from django.template.loader import get_template
from django.test import SimpleTestCase

from .admin import NewsAdmin, NewsAdminForm
from .models import News


class AdminJavascriptFallbackTests(SimpleTestCase):
    def test_public_site_script_is_available_through_django(self):
        response = self.client.get('/static/news-site.js')

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response['Content-Type'])
        self.assertIn(b'data-menu-trigger', b''.join(response.streaming_content))

    def test_public_page_uses_the_current_menu_script(self):
        response = get_template('base.html').render({})

        self.assertIn('/static/news-site.css?v=6', response)
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
