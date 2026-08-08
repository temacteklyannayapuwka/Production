from django.test import SimpleTestCase

from .admin import NewsAdminForm


class AdminJavascriptFallbackTests(SimpleTestCase):
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


class EditorialAdminTests(SimpleTestCase):
    def test_new_news_form_starts_as_a_draft_with_editorial_help(self):
        form = NewsAdminForm()

        self.assertFalse(form.fields['is_published'].initial)
        self.assertEqual(form.fields['main_photo'].label, 'Главное фото')
        self.assertIn('WebP', form.fields['main_photo'].help_text)
        self.assertIn('Основной текст', form.fields['content'].help_text)
