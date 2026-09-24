import json
import re
from datetime import timedelta
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, News, Tag


@override_settings(
    DEBUG=False,
    PUBLIC_SITE_URL="https://stavplus.ru",
    SEO_NOINDEX_HOSTS={"new.stavplus.ru"},
)
class TechnicalSEOTests(TestCase):
    host = "stavplus.ru"

    def setUp(self):
        self.category = Category.objects.create(
            name="Общество",
            slug="obshchestvo",
            description="Новости общества и городской жизни.",
        )
        self.tag = Tag.objects.create(name="Город", slug="gorod")
        self.article = self.create_news(
            "public-story",
            title="В Ставрополе открыли новый городской маршрут",
            main_photo="news/main/2026/09/public-story.webp",
        )
        self.article.tags.add(self.tag)

    def create_news(self, slug, **overrides):
        values = {
            "title": f"Новость {slug}",
            "slug": slug,
            "content": "<p>Проверяемый текст новости.</p>",
            "excerpt": "Краткое и уникальное описание новости.",
            "category": self.category,
            "editorial_status": News.EditorialStatus.PUBLISHED,
            "date_start": timezone.now() - timedelta(hours=1),
        }
        values.update(overrides)
        return News.objects.create(**values)

    def get(self, path, **extra):
        return self.client.get(path, HTTP_HOST=self.host, **extra)

    @staticmethod
    def json_ld_blocks(response):
        source = response.content.decode()
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            source,
            flags=re.DOTALL,
        )
        return [json.loads(block) for block in blocks]

    def test_robots_lists_public_sitemaps_and_protects_technical_urls(self):
        response = self.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /ckeditor/")
        self.assertContains(response, "Search stays crawlable")
        self.assertNotContains(response, "Disallow: /search/")
        self.assertContains(response, "Allow: /static/")
        self.assertContains(response, "Allow: /media/")
        self.assertContains(response, "Sitemap: https://stavplus.ru/sitemap.xml")
        self.assertContains(
            response,
            "Sitemap: https://stavplus.ru/news-sitemap.xml",
        )

        preview = self.client.get("/robots.txt", HTTP_HOST="new.stavplus.ru")
        self.assertContains(preview, "Allow: /")
        self.assertContains(preview, "X-Robots-Tag: noindex, nofollow")
        self.assertEqual(preview["X-Robots-Tag"], "noindex, nofollow")

    def test_sitemap_contains_only_canonical_current_public_content(self):
        draft = self.create_news(
            "draft-story",
            editorial_status=News.EditorialStatus.DRAFT,
        )
        future = self.create_news(
            "future-story",
            editorial_status=News.EditorialStatus.SCHEDULED,
            date_start=timezone.now() + timedelta(days=1),
        )
        expired = self.create_news(
            "expired-story",
            date_end=timezone.now() - timedelta(minutes=1),
        )

        response = self.get(reverse("sitemap"))
        root = ElementTree.fromstring(response.content)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {node.text for node in root.findall("sm:url/sm:loc", namespace)}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        self.assertIn("https://stavplus.ru/", locations)
        self.assertIn(
            f"https://stavplus.ru{self.article.get_absolute_url()}",
            locations,
        )
        self.assertIn("https://stavplus.ru/rubric/obshchestvo/", locations)
        self.assertIn("https://stavplus.ru/tag/gorod/", locations)
        for hidden in (draft, future, expired):
            self.assertNotIn(
                f"https://stavplus.ru{hidden.get_absolute_url()}",
                locations,
            )
        self.assertNotIn("https://stavplus.ru/search/", locations)
        self.assertNotIn("https://stavplus.ru/obshchestvo/", locations)

    def test_google_news_sitemap_contains_only_last_two_days(self):
        old_article = self.create_news(
            "old-story",
            date_start=timezone.now() - timedelta(days=3),
        )

        response = self.get(reverse("news_sitemap"))
        source = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("xmlns:news=", source)
        self.assertIn(self.article.get_absolute_url(), source)
        self.assertNotIn(old_article.get_absolute_url(), source)
        self.assertIn("<news:name>Ставрополь+</news:name>", source)
        self.assertIn("<news:language>ru</news:language>", source)

    def test_article_has_canonical_social_metadata_and_valid_json_ld(self):
        response = self.get(self.article.get_absolute_url())
        source = response.content.decode()

        self.assertContains(
            response,
            f'<link rel="canonical" href="https://stavplus.ru{self.article.get_absolute_url()}">',
            html=True,
        )
        self.assertIn('<meta property="og:type" content="article">', source)
        self.assertIn(
            '<meta property="og:image" content="https://stavplus.ru/media/news/main/2026/09/public-story.webp">',
            source,
        )
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', source)
        self.assertIn(f"<title>{self.article.meta_title} — Ставрополь+</title>", source)
        self.assertIn(
            f'<meta name="description" content="{self.article.meta_description}">',
            source,
        )

        blocks = self.json_ld_blocks(response)
        self.assertTrue(blocks)
        for block in blocks:
            json.dumps(block)
        graph = blocks[0]["@graph"]
        types = {item["@type"] for item in graph}
        self.assertSetEqual(
            types,
            {"NewsMediaOrganization", "BreadcrumbList", "NewsArticle"},
        )
        news_schema = next(item for item in graph if item["@type"] == "NewsArticle")
        self.assertEqual(news_schema["headline"], self.article.title)
        self.assertEqual(
            news_schema["mainEntityOfPage"]["@id"],
            f"https://stavplus.ru{self.article.get_absolute_url()}",
        )
        self.assertEqual(news_schema["publisher"]["@id"], "https://stavplus.ru/#organization")

    def test_home_category_and_tag_have_distinct_indexable_metadata(self):
        paths = (
            reverse("index"),
            reverse("category", args=(self.category.slug,)),
            reverse("tag", args=(self.tag.slug,)),
        )
        titles = set()
        for path in paths:
            with self.subTest(path=path):
                response = self.get(path)
                source = response.content.decode()
                title = re.search(r"<title>(.*?)</title>", source).group(1)
                titles.add(title)
                self.assertIn(
                    f'<link rel="canonical" href="https://stavplus.ru{path}">',
                    source,
                )
                self.assertIn('<meta name="robots" content="index,follow">', source)
                for block in self.json_ld_blocks(response):
                    json.dumps(block)
        self.assertEqual(len(titles), len(paths))

    def test_category_pagination_uses_a_self_canonical_without_extra_parameters(self):
        for number in range(21):
            self.create_news(f"page-{number}")

        response = self.get(
            reverse("category", args=(self.category.slug,)),
            data={"page": 2, "utm_source": "ignored"},
        )

        self.assertContains(
            response,
            '<link rel="canonical" href="https://stavplus.ru/rubric/obshchestvo/?page=2">',
            html=True,
        )
        self.assertContains(response, "страница 2")
        self.assertNotContains(response, "utm_source")

    def test_search_is_noindex_and_does_not_canonicalize_the_query(self):
        response = self.get(reverse("search"), data={"q": "Ставрополь"})
        source = response.content.decode()

        self.assertIn('<meta name="robots" content="noindex,follow">', source)
        self.assertIn(
            '<link rel="canonical" href="https://stavplus.ru/search/">',
            source,
        )
        self.assertNotIn("?q=", source.split('<link rel="canonical"', 1)[1].split(">", 1)[0])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_legacy_section_and_index_filenames_redirect_permanently(self):
        section = self.get("/obshchestvo/")
        html_index = self.get("/index.html")
        php_index = self.get("/index.php")

        self.assertRedirects(
            section,
            "/rubric/obshchestvo/",
            status_code=301,
            fetch_redirect_response=False,
        )
        for response in (html_index, php_index):
            self.assertRedirects(
                response,
                "/",
                status_code=301,
                fetch_redirect_response=False,
            )

        www_response = self.client.get(
            "/rubric/obshchestvo/?page=2",
            HTTP_HOST="www.stavplus.ru",
        )
        self.assertRedirects(
            www_response,
            "https://stavplus.ru/rubric/obshchestvo/?page=2",
            status_code=301,
            fetch_redirect_response=False,
        )

    def test_unknown_and_unpublished_news_return_a_real_custom_404(self):
        draft = self.create_news(
            "private-draft",
            editorial_status=News.EditorialStatus.DRAFT,
        )

        for path in ("/missing-page/", draft.get_absolute_url()):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertContains(response, "Страница не найдена", status_code=404)
                self.assertContains(
                    response,
                    '<meta name="robots" content="noindex,follow">',
                    status_code=404,
                    html=True,
                )
                self.assertContains(
                    response,
                    f'<link rel="canonical" href="https://stavplus.ru{path}">',
                    status_code=404,
                    html=True,
                )
                self.assertEqual(response["X-Robots-Tag"], "noindex, follow")

    def test_article_without_photo_uses_an_absolute_fallback_image(self):
        text_only = self.create_news("text-only", main_photo=None)

        response = self.get(text_only.get_absolute_url())
        source = response.content.decode()

        fallback = "https://stavplus.ru/static/hero/stavropol-aerial.webp"
        self.assertIn(f'<meta property="og:image" content="{fallback}">', source)
        schema = next(
            item
            for item in self.json_ld_blocks(response)[0]["@graph"]
            if item["@type"] == "NewsArticle"
        )
        self.assertEqual(schema["image"], [fallback])

    def test_admin_is_protected_by_an_http_noindex_header(self):
        response = self.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_editorial_h1_in_body_is_demoted_below_the_page_title(self):
        article = self.create_news(
            "stored-h1",
            content="<h1>Внутренний заголовок</h1><p>Текст.</p>",
        )

        response = self.get(article.get_absolute_url())
        source = response.content.decode()

        self.assertEqual(source.count("<h1"), 1)
        self.assertIn("<h2>Внутренний заголовок</h2>", source)
