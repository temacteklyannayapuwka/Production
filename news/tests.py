from django.test import SimpleTestCase


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
