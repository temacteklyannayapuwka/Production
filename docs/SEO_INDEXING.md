# Индексация и техническое SEO «Ставрополь+»

Канонический публичный origin задаётся безопасной переменной:

```env
PUBLIC_SITE_URL=https://stavplus.ru
```

По умолчанию приложение считает `stavplus.ru` основным сайтом. Запросы к
`www.stavplus.ru` получают постоянный `301` на адрес без `www`, а тестовый
`new.stavplus.ru` — `X-Robots-Tag: noindex, nofollow`. Его robots разрешает
обход, чтобы робот увидел HTTP noindex: один robots-запрет не гарантирует
удаление URL из индекса. Эти правила не заменяют серверный HTTP→HTTPS-редирект
в Nginx.

## Быстрая проверка после деплоя

```bash
curl -i https://stavplus.ru/robots.txt
curl -i https://stavplus.ru/sitemap.xml
curl -i https://stavplus.ru/news-sitemap.xml
curl -I https://www.stavplus.ru/
curl -I https://stavplus.ru/obshchestvo/
curl -I https://stavplus.ru/definitely-missing/
```

Ожидается:

- `robots.txt` — `200`, запрет `/admin/` и `/ckeditor/`, явное пояснение для
  crawlable `/search/` с noindex и две абсолютные строки `Sitemap`;
- обычная и новостная карты — `200 application/xml` и только URL
  `https://stavplus.ru/...`;
- `www` и legacy-рубрики — один `301` без цепочки и цикла;
- неизвестный URL — настоящий `404`, а не `200` с текстом ошибки.

## Метатеги и JSON-LD

На главной, новости, рубрике, теге, поиске, пагинации и 404 откройте исходный
HTML и проверьте ровно по одному `title`, description, robots и canonical,
затем `og:*` и `twitter:*`. Canonical не должен переносить UTM и случайные
query-параметры; для второй и следующих страниц рубрики/тега сохраняется только
`?page=N`. Поиск всегда остаётся `noindex,follow`.

JSON-LD можно извлечь из каждого
`<script type="application/ld+json">` и проверить:

- локально — `json.loads()` (это уже покрыто тестом);
- после деплоя — [Google Rich Results Test](https://search.google.com/test/rich-results)
  и инспекцией URL в Search Console;
- словарь типов — [Schema.org validator](https://validator.schema.org/).

Для статьи ожидаются `NewsArticle`, `NewsMediaOrganization` и
`BreadcrumbList`. Если у новости нет фото, используется абсолютный URL
резервного WebP; выдуманные контакты, адрес и персональный автор не добавляются.

## PageSpeed после деплоя

В [PageSpeed Insights](https://pagespeed.web.dev/) отдельно проверить mobile и
desktop минимум для:

- `https://stavplus.ru/`;
- действующей рубрики, например `https://stavplus.ru/rubric/obshchestvo/`;
- действующей новости из `sitemap.xml`.

Для каждого прогона записать дату, URL, режим, Performance, Accessibility,
Best Practices, SEO, LCP, CLS и INP. Если полевых данных CrUX нет, так и
записать; лабораторный TBT не выдавать за INP. После прогрева кеша выполнить не
менее трёх прогонов и сравнивать медиану, а не лучший результат.

## Google Search Console

Действия выполняет владелец или пользователь с полным доступом:

1. добавить Domain property `stavplus.ru` и подтвердить её через DNS;
2. при необходимости отдельно проверить URL-prefix свойства
   `https://stavplus.ru/` и `https://new.stavplus.ru/`;
3. отправить `sitemap.xml` и `news-sitemap.xml`;
4. через URL Inspection проверить главную, рубрику и свежую новость, затем
   запросить переобход этих ключевых страниц;
5. проверить Page indexing, Crawl stats, Core Web Vitals и ошибки Article /
   Breadcrumb;
6. после окончательного переноса с `new` убедиться в постраничных `301`,
   canonical на основной домен и отсутствии `new` в sitemap.

## Яндекс Вебмастер

1. добавить точное зеркало `https://stavplus.ru`;
2. подтвердить права DNS, HTML-файлом или meta-тегом владельца;
3. проверить robots и добавить обе карты сайта;
4. отправить главную, важные рубрики и свежие новости в «Переобход страниц»;
5. контролировать «Страницы в поиске», исключённые URL, обход и диагностику;
6. после переноса проверить главное зеркало, `301` с `www`/`new` и совпадение
   canonical с sitemap.

## Откат

Миграций БД нет. При критической проблеме вернуть приложение на базовый SHA
`3ea19ea209969982e260b6a2327266f84c423a2d`, перезапустить только его процесс и
проверить главную/новость/админку. После отката `robots.txt`, sitemap и новые
метаданные исчезнут, поэтому это аварийная мера; данные новостей не меняются.
Не удаляйте вручную записи из Google или Яндекса без отдельного анализа.

Полная матрица аудита, baseline и ручные действия находятся в
[`reports/SEO_AUDIT_STAVPLUS_2026-09-22.md`](reports/SEO_AUDIT_STAVPLUS_2026-09-22.md).
