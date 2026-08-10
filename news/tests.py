from datetime import timedelta

from django.contrib import admin
from django.core.management import call_command
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .admin import NewsAdmin, NewsAdminForm
from .models import Advertisement, Category, News
from .views import published_news


class AdminJavascriptFallbackTests(SimpleTestCase):
    def test_public_site_script_is_available_through_django(self):
        response = self.client.get('/static/news-site.js')

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response['Content-Type'])
        self.assertIn(b'data-menu-trigger', b''.join(response.streaming_content))

    def test_public_page_uses_the_current_menu_script(self):
        response = get_template('base.html').render({})

        self.assertIn('/static/news-site.css?v=40', response)
        self.assertIn('family=Merriweather', response)
        self.assertIn('content="#151515"', response)
        self.assertNotIn('family=Playfair+Display', response)
        self.assertNotIn('family=Golos+Text', response)
        self.assertNotIn('family=Prata', response)
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
        self.assertContains(response, '--color-primary-600: rgb(55, 55, 55)')


class EditorialAdminTests(SimpleTestCase):
    def test_new_news_form_starts_as_a_draft_with_editorial_help(self):
        form = NewsAdminForm()

        self.assertEqual(form.fields['editorial_status'].initial, News.EditorialStatus.DRAFT)
        self.assertEqual(form.fields['main_photo'].label, 'Главное фото')
        self.assertIn('WebP', form.fields['main_photo'].help_text)
        self.assertIn('весь экран', form.fields['content'].help_text)
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
        self.assertNotIn('advertisements.home_bottom', source)
        self.assertNotIn('advertisements.home_popular', source)
        self.assertEqual(source.count('advertisements.home_sidebar'), 1)
        self.assertIn('hero__lead', source)
        self.assertIn('popular--sticky', source)
        self.assertIn('latest--feed', source)
        self.assertLess(source.index('popular--sticky'), source.index('home-main'))
        self.assertGreater(source.index('latest--feed'), source.index('home-main__feed'))
        self.assertIn('Погода · Ставрополь', source)

    def test_category_page_uses_a_sticky_news_feed_without_lower_advertisements(self):
        source = get_template('category.html').template.source

        self.assertIn('rubric-rail--sticky', source)
        self.assertIn('rubric-feed-scroll', source)
        self.assertIn('latest_news', source)
        self.assertIn('rubric-row__excerpt', source)
        self.assertIn('Лента новостей', source)
        self.assertNotIn('popular_news', source)
        self.assertNotIn('section_rail', source)
        self.assertNotIn('section_bottom', source)
        self.assertNotIn('Главное за день — в одном письме', source)

    def test_view_counts_are_only_visible_in_the_homepage_top_block(self):
        index_source = get_template('index.html').template.source

        self.assertEqual(index_source.count('news.views'), 1)
        self.assertIn('popular_news', index_source)
        self.assertIn('Топ по просмотрам', index_source)
        self.assertIn('headline-list__excerpt', index_source)
        self.assertIn('Лента новостей', index_source)
        self.assertIn('Категории', index_source)
        category_source = get_template('category.html').template.source
        self.assertEqual(category_source.count('news.views'), 0)
        self.assertIn('latest_news', category_source)

        for template_name in ('article.html', 'search.html'):
            self.assertNotIn(
                '.views',
                get_template(template_name).template.source,
            )

    def test_templates_render_advertising_slots_and_article_gallery(self):
        self.assertIn('components/ad_slot.html', get_template('index.html').template.source)
        article_source = get_template('article.html').template.source
        self.assertIn('article.gallery.all', article_source)
        self.assertIn('Лента новостей', article_source)
        self.assertIn('article-news-feed', article_source)
        self.assertIn('news_feed', article_source)
        self.assertIn('continuation_articles', article_source)
        self.assertIn('next_category_article', article_source)
        self.assertNotIn('<span>Сейчас</span>', article_source)
        self.assertIsNotNone(get_template('components/ad_slot.html'))


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
            editorial_status=News.EditorialStatus.PUBLISHED,
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

    def test_admin_list_allows_inline_status_and_featured_selection(self):
        model_admin = NewsAdmin(News, admin.site)

        self.assertIn('editorial_status', model_admin.list_editable)
        self.assertIn('is_featured', model_admin.list_editable)

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
        self.assertEqual(len(response.context['popular_news']), 8)


class LocalDemoImportTests(TestCase):
    def test_local_demo_import_parses_fixture_dates_and_creates_text_only_news(self):
        call_command('import_local_demo')

        self.assertEqual(News.objects.count(), 33)
        text_only_news = News.objects.get(slug='stavropol-community-sports-space')
        self.assertFalse(text_only_news.main_photo)
        self.assertTrue(timezone.is_aware(text_only_news.date_start))
        self.assertGreaterEqual(text_only_news.content.count('<p>'), 3)


class ArticleContinuationTests(TestCase):
    def setUp(self):
        self.society = Category.objects.create(name='Общество', slug='obshchestvo')
        self.politics = Category.objects.create(name='Политика', slug='politika')
        self.economy = Category.objects.create(name='Экономика', slug='ekonomika')

    def create_news(self, slug, category, position):
        return News.objects.create(
            title=f'Новость {slug}',
            slug=slug,
            content=f'<p>Полный текст материала {slug}.</p>',
            excerpt=f'Короткий анонс материала {slug}.',
            category=category,
            editorial_status=News.EditorialStatus.PUBLISHED,
            date_start=timezone.now() - timedelta(minutes=position),
        )

    def test_article_continues_with_nine_other_materials_from_its_category(self):
        society_news = [
            self.create_news(f'society-{position}', self.society, position)
            for position in range(1, 12)
        ]
        politics_first = self.create_news('politics-1', self.politics, 2)
        economy_first = self.create_news('economy-1', self.economy, 1)

        response = self.client.get(society_news[2].get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['article_sequence_number'], 3)
        self.assertEqual(len(response.context['continuation_articles']), 9)
        self.assertEqual(
            [item['position'] for item in response.context['continuation_articles']],
            [1, 2, 4, 5, 6, 7, 8, 9, 10],
        )
        self.assertNotIn(
            society_news[2].pk,
            [item['news'].pk for item in response.context['continuation_articles']],
        )
        self.assertEqual(response.context['next_category_article'], politics_first)
        self.assertContains(response, 'Продолжение ленты')
        self.assertContains(response, 'Материал №04')

        economy_response = self.client.get(economy_first.get_absolute_url())
        self.assertEqual(
            economy_response.context['next_category_article'],
            society_news[0],
        )


class EditorialStatusAndSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Общество', slug='obshchestvo')

    def create_news(self, slug, **overrides):
        values = {
            'title': 'Новости Ставрополя: общественное пространство',
            'slug': slug,
            'content': '<p>Город Ставрополь получил общественное пространство для прогулок и встреч.</p>',
            'excerpt': 'Новый городской маршрут появился в центре Ставрополя.',
            'category': self.category,
            'editorial_status': News.EditorialStatus.PUBLISHED,
            'date_start': timezone.now() - timedelta(minutes=5),
        }
        values.update(overrides)
        return News.objects.create(**values)

    def test_status_controls_publication_flags(self):
        draft = self.create_news('draft', editorial_status=News.EditorialStatus.DRAFT)
        scheduled = self.create_news(
            'scheduled',
            editorial_status=News.EditorialStatus.SCHEDULED,
            date_start=timezone.now() + timedelta(hours=2),
        )

        self.assertFalse(draft.is_published)
        self.assertTrue(scheduled.is_published)
        self.assertFalse(draft.is_active)
        self.assertFalse(scheduled.is_active)

    def test_search_shows_match_source_context_and_highlight(self):
        self.create_news('stavropol-search')

        response = self.client.get('/search/', {'q': 'Ставрополь'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Найдено в:')
        self.assertContains(response, 'class="search-highlight">Ставрополь</mark>', html=False)
        self.assertContains(response, 'общественное пространство')

    def test_active_banner_is_available_to_the_homepage(self):
        banner = Advertisement.objects.create(
            name='Верхний баннер',
            placement=Advertisement.Placement.TOP,
            image='advertising/test.webp',
        )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['advertisements']['top'], banner)
