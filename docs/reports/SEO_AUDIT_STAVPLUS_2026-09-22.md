# SEO-аудит и подготовка индексации «Ставрополь+»

Дата начала проверки: **22.09.2026**. Продолжение и актуализация HTTP-проверок:
**24.09.2026**. Ветка: `feature/seo-indexing-audit`. База:
`3ea19ea209969982e260b6a2327266f84c423a2d` (`feature/ai-news-pipeline`).
Деплой, merge и действия в аккаунтах владельца не выполнялись.

## Итог для владельца

В ветке подготовлены технические условия для индексации: централизованные
метаданные, canonical, Open Graph/Twitter, безопасный JSON-LD, `robots.txt`,
обычная sitemap, отдельная Google News sitemap, настоящий 404 и постоянные
редиректы legacy URL. Поиск и административные страницы защищены от
индексации. Черновики, будущие и завершившиеся публикации не попадают в карты.

Публичный сайт пока работает на прежнем коде: на момент проверки
`https://stavplus.ru/robots.txt` и `/sitemap.xml` возвращали `404`. Поэтому
результат станет виден поисковикам только после отдельного разрешённого merge и
деплоя. Автоматической публикации новостей и изменений production в рамках
этой работы не было.

## Использованные источники

Оба Excel-файла прочитаны полностью, включая все листы и все непустые ячейки;
исходники не изменялись:

- `SEO_чек-лист_sad-restoran.ru.xlsx`: 4 видимых листа — «Чек-лист SEO»
  (29 проверок), «SEO по страницам» (18 страниц), «Семантическое ядро»
  (24 кластера), «Рекомендации» (17 пунктов);
- `Изменённый чек-лист.xlsx`: 1 видимый лист, 18 проверок внутренней
  оптимизации; размер листа `A1:E1003`, содержательные строки заканчиваются на
  строке 37, остальные ячейки пусты/оформительские.

Содержимое таблиц использовалось только как структура аудита. Устаревшие или
неподходящие советы (например, обязательный `.ico`, `Host` в robots, точная
«SEO-длина» description, Restaurant/LocalBusiness, корзина и бронирование) не
считались актуальными требованиями без подтверждения официальной документацией.

Коды официальных источников в матрице:

- **G-ROBOTS** — [Google: robots.txt](https://developers.google.com/search/docs/crawling-indexing/robots/intro);
- **G-SITEMAP** — [Google: создание и отправка sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap);
- **G-NEWS** — [Google: News sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap);
- **G-CANON** — [Google: canonicalization](https://developers.google.com/search/docs/crawling-indexing/canonicalization);
- **G-META** — [Google: поддерживаемые meta robots](https://developers.google.com/search/docs/crawling-indexing/special-tags);
- **G-TITLE** — [Google: title links](https://developers.google.com/search/docs/appearance/title-link);
- **G-SNIPPET** — [Google: snippets и meta description](https://developers.google.com/search/docs/appearance/snippet);
- **G-ARTICLE** — [Google: Article / NewsArticle](https://developers.google.com/search/docs/appearance/structured-data/article);
- **G-BREADCRUMB** — [Google: BreadcrumbList](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb);
- **G-IMAGE** — [Google: image SEO](https://developers.google.com/search/docs/appearance/google-images);
- **G-LINKS** — [Google: crawlable links и анкоры](https://developers.google.com/search/docs/crawling-indexing/links-crawlable);
- **G-RECRAWL** — [Google: запрос переобхода](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl);
- **WEB-VITALS** — [web.dev: измерение Web Vitals](https://web.dev/articles/vitals-measurement-getting-started) и [workflow Google](https://web.dev/articles/vitals-tools);
- **DJ-SITEMAP** — [Django 6.0 sitemap framework](https://docs.djangoproject.com/en/6.0/ref/contrib/sitemaps/);
- **SCHEMA** — [Schema.org NewsArticle](https://schema.org/NewsArticle), [NewsMediaOrganization](https://schema.org/NewsMediaOrganization), [BreadcrumbList](https://schema.org/BreadcrumbList);
- **Y-START** — [Яндекс Вебмастер: начало работы](https://yandex.ru/support/webmaster/ru/service/quick-start);
- **Y-RIGHTS** — [Яндекс: подтверждение прав](https://yandex.ru/support/webmaster/ru/service/rights);
- **Y-SITEMAP** — [Яндекс: Sitemap](https://yandex.ru/support/webmaster/ru/controlling-robot/sitemap);
- **Y-CANON** — [Яндекс: canonical](https://yandex.ru/support/webmaster/ru/robot-workings/canonical);
- **Y-REINDEX** — [Яндекс: переобход страниц](https://yandex.ru/support/webmaster/ru/robot-workings/site-reindex).

Обозначения исходных таблиц: **XLSX-R** — ресторанный чек-лист,
**XLSX-G** — изменённый общий чек-лист.

## Как определён production

| Проверка | Результат 22–24.09.2026 |
|---|---|
| Конфигурация | `ecosystem.config.js` называет процесс `stavplus.ru`; README задаёт production-hosts `stavplus.ru,www.stavplus.ru`; `new.stavplus.ru` документирован как отдельный тестовый контур. |
| `https://stavplus.ru/` | `200`, Nginx 1.23.1, текущая публичная версия с демо/редакционными материалами. |
| `https://new.stavplus.ru/` | `200`, отдельная база/версия редизайна; это не основное зеркало. |
| robots/sitemap | На обоих доменах `/robots.txt` и `/sitemap.xml` возвращали `404`. |
| Метаданные | Обе главные имели общий title/description, но без canonical, OG, Twitter и JSON-LD. |
| `https://www.stavplus.ru/` | `200` без редиректа на адрес без `www`: подтверждённый риск дубля. В ветке добавлен точный app-level `301`; после деплоя предпочтительно дублировать правило в Nginx. |
| `http://stavplus.ru/` | HTTP-запрос завершился timeout через 30 секунд; состояние HTTP→HTTPS требует серверной проверки. |

Канонический origin в коде установлен как `https://stavplus.ru`. Он берётся из
`PUBLIC_SITE_URL`, а не из входного Host. Для `new.stavplus.ru` ветка отдаёт
`noindex, nofollow`; robots оставляет его доступным для обхода, чтобы робот
увидел HTTP noindex. После окончательного переноса тестовый поддомен должен
получить постраничные `301` на основной домен на уровне Nginx.

## Реализованная схема

```text
request
  ├─ www.stavplus.ru → 301 → https://stavplus.ru/<тот же path/query>
  ├─ new.stavplus.ru → HTTP noindex (robots разрешает прочитать директиву)
  └─ stavplus.ru
       ├─ view формирует единый SEO-context
       ├─ base.html: title/description/robots/canonical/OG/Twitter
       ├─ безопасно сериализованный JSON-LD
       ├─ sitemap.xml: home + текущие News + активные рубрики/теги
       └─ news-sitemap.xml: не более 1000 News за последние 2 суток
```

## Матрица проверки

«До» относится к SHA `3ea19ea`; «после» — к текущей ветке, до деплоя.

| Раздел | Проверка | Источник требования | Состояние до изменений | Найденное доказательство | Внесённое изменение | Состояние после изменений | Приоритет | Способ проверки | Оставшиеся ручные действия |
|---|---|---|---|---|---|---|---|---|---|
| Индексация | `robots.txt` | G-ROBOTS, G-SITEMAP, Y-SITEMAP, XLSX-R, XLSX-G | Не выполнено | Оба публичных endpoint отдавали 404 | Динамический robots; закрыты admin/ckeditor; search оставлен crawlable для чтения noindex; открыты public static/media; указаны две sitemap | Выполнено | P0 | `curl -i /robots.txt`, автотест | После деплоя проверить в GSC и Яндекс Вебмастере |
| Индексация | Обычная sitemap | G-SITEMAP, DJ-SITEMAP, Y-SITEMAP, XLSX-R, XLSX-G | Не выполнено | `/sitemap.xml` = 404 | Django Sitemap classes; только canonical public URLs, реальный `updated_at` новости | Выполнено | P0 | XML parse, автотест | Отправить владельцем в обе системы |
| Индексация | Google News sitemap | G-NEWS | Не выполнено | Отдельной карты не было | `/news-sitemap.xml`, только последние 2 суток, лимит 1000, publication/name/language/title | Выполнено | P1 | XML + автотест; GSC | Проверить обработку после деплоя; карта помогает обнаружению, но не гарантирует показ в Google News |
| Дубли | Canonical | G-CANON, Y-CANON, XLSX-R, XLSX-G | Не выполнено | `rel=canonical` отсутствовал | Self-canonical на индексируемых страницах; доверенный public origin; query очищаются | Выполнено | P0 | исходный HTML, тест | Инспекция выбранного canonical в GSC/Яндекс после обхода |
| Дубли | `www` → без `www` | G-CANON, XLSX-G | Не выполнено | `www` возвращал 200 | Точный app-level 301 с сохранением path/query | Выполнено | P0 | автотест, `curl -I` | Добавить/проверить эквивалент в Nginx, исключить цепочку |
| Дубли | HTTP → HTTPS | G-CANON, XLSX-G | Не выполнено | HTTP endpoint timeout | Код генерирует только HTTPS canonical; серверное правило не менялось | Требует проверки на продакшене | P0 | `curl -IL http://stavplus.ru/` | Владелец/администратор Nginx должен обеспечить один 301 |
| Дубли | Legacy-рубрики | G-CANON, Y-CANON | Не выполнено | `/obshchestvo/` и аналоги рендерили копию canonical-рубрики с 200 | Семь legacy путей дают безопасный 301 только при существующей активной рубрике | Выполнено | P0 | автотест всех маршрутов/выборочно curl | После деплоя проверить старые реальные URL из аналитики |
| Дубли | `/index.html`, `/index.php` | XLSX-G, G-CANON | Не выполнено | Явных правил не было | Оба пути дают 301 на `/` | Выполнено | P1 | автотест | Проверить отсутствие более раннего Nginx-правила/цепочки |
| Метаданные | Уникальный Title | G-TITLE, XLSX-R, XLSX-G | Частично | Главная/шаблоны имели title, пагинация и 404 не различались | Централизованный page-specific title для всех типов, номер страницы в пагинации | Выполнено | P1 | HTML + тест | Редактору контролировать `meta_title` популярных новостей |
| Метаданные | Description | G-SNIPPET, XLSX-R, XLSX-G | Частично | Был общий default и article override | Уникальные описания из полей/описаний страниц, нормализация plain text и безопасное ограничение | Выполнено | P1 | HTML + тест | Проверить реальные сниппеты: поисковики могут выбрать другой текст |
| Метаданные | `meta robots` | G-META | Не выполнено | Тег отсутствовал | `index,follow` для публичных; `noindex,follow` для поиска/404 | Выполнено | P0 | HTML + тест | Инспекция URL после деплоя |
| Social | Open Graph | G-IMAGE, XLSX-G | Не выполнено | `og:*` отсутствовал | type/title/description/url/image/site_name/locale + article timestamps/section | Выполнено | P1 | HTML + тест, Telegram/VK preview | Очистить кеш превью соцсетей после деплоя при необходимости |
| Social | Twitter Card | Практика social preview | Не выполнено | Twitter meta отсутствовали | `summary_large_image`, title/description/image | Выполнено | P2 | HTML + тест | Ручной preview после деплоя |
| Schema.org | `NewsArticle` | G-ARTICLE, SCHEMA | Не выполнено | JSON-LD отсутствовал | headline, description, absolute image, dates, page, author, publisher/logo, section, URL; AI-source как `isBasedOn` | Выполнено | P1 | каждый script парсится JSON; Rich Results Test | Проверить deployed URL; rich result не гарантируется |
| Schema.org | `NewsMediaOrganization` | SCHEMA, XLSX-G | Не выполнено | Organization schema отсутствовала | Название, URL и существующий официальный SVG-логотип; неизвестные контакты не выдуманы | Выполнено | P1 | JSON parse, Schema validator | Владелец может отдельно подтвердить юридические реквизиты и редакционные policies |
| Schema.org | `BreadcrumbList` | G-BREADCRUMB, SCHEMA, XLSX-R | Не выполнено | Визуальные breadcrumbs были только у статьи | JSON-LD для новости/рубрики/тега; видимые breadcrumbs добавлены рубрике и тегу | Выполнено | P1 | JSON parse + HTML | Rich Results Test после деплоя |
| Структура | Один H1 | G-TITLE, XLSX-R | Частично | Page templates имели H1, но редакторский HTML мог добавить ещё один | Сохранён один page H1; H1 из тела материала при выводе понижается до H2 | Выполнено | P1 | автотест, HTML outline | Редакционная проверка старых материалов со сложной разметкой |
| Структура | Логичные H2–H3 | XLSX-R | Частично | Основные шаблоны семантичны, legacy-body не гарантирован | Основной H1 и серверная иерархия сохранены; body H1 нормализован | Частично | P2 | ручной outline выборки старых статей | Исправить некорректные H2/H3 в архиве по данным crawler |
| HTML | `main`, `article`, `nav`, `time` | G-LINKS, accessibility practice | Частично | Большинство элементов уже были; поиск выводил дату без `<time>` | Поиск получил machine-readable datetime; семантика страниц сохранена | Выполнено | P2 | HTML validation | Проверить W3C/Nu validator после деплоя |
| Изображения | ALT | G-IMAGE, XLSX-R, XLSX-G | Частично | Карточки рубрики/тега/поиска имели пустой alt | Контентные карточки используют title; декоративные иконки сохраняют пустой alt | Выполнено | P1 | шаблоны + ручной screen reader | Редактору писать подписи галереи вместо повторения title |
| Изображения | Width/height и CLS | WEB-VITALS, XLSX-R, XLSX-G | Частично | У hero были размеры, у media/галерей — нет | Intrinsic width/height добавляются, когда storage может прочитать файл; CSS-контейнеры имеют устойчивые размеры | Частично | P1 | HTML на реальных media + Lighthouse CLS | Проверить legacy/missing media на production; при необходимости хранить размеры в БД отдельной миграцией |
| Изображения | WebP/AVIF | G-IMAGE, XLSX-R, XLSX-G | Частично | Hero — WebP; новые загрузки конвертируются; legacy и social встречаются JPG | Повторная массовая конвертация не выполнялась; существующий безопасный WebP pipeline сохранён | Частично | P2 | `file`, Network panel | Отдельно инвентаризировать тяжёлые legacy JPG; не делать массовую замену без backup |
| Изображения | Lazy-load/LCP | G-IMAGE, WEB-VITALS, XLSX-R | Частично | Главный static hero eager; вторичные фото lazy; часть фото зависела от JS deferred-src | Вторичные фото используют native `src` + `loading=lazy`; главный hero/article image не lazy и имеет high priority | Выполнено | P1 | HTML, Network/Lighthouse | Подтвердить реальный LCP элемент после деплоя |
| Производительность | LCP | WEB-VITALS, XLSX-R | Не выполнено | PSI API вернул 429; баллов нет | Убрана JS-зависимость вторичных изображений, LCP-ресурсы остаются eager/preload | Требует проверки на продакшене | P1 | PSI mobile/desktop | Выполнить 3 прогона на трёх типах страниц |
| Производительность | CLS | WEB-VITALS, XLSX-R | Не выполнено | Полевых/лабораторных значений нет | Сохранены размеры hero и aspect-ratio контейнеров; intrinsic media dimensions где доступны | Требует проверки на продакшене | P1 | PSI/Lighthouse/CrUX | Зафиксировать число, не только score |
| Производительность | INP | WEB-VITALS | Не выполнено | Полевые данные недоступны | JS-функциональность не расширялась | Требует проверки на продакшене | P1 | CrUX/PSI; TBT только lab proxy | Дождаться достаточных полевых данных или подключить RUM отдельно |
| Mobile | Мобильная версия | WEB-VITALS, XLSX-R | Частично | Responsive CSS и viewport уже были | Дизайн не менялся; SEO-head не зависит от viewport | Частично | P1 | реальные устройства + PSI mobile | Визуальный smoke-test после деплоя |
| HTTP | Настоящий 404 | G-META, XLSX-G | Частично | Framework 404 был англоязычным, SEO-meta отсутствовали | Кастомная русская 404, статус 404, noindex meta/header, ссылка на главную | Выполнено | P0 | автотест | Проверить Nginx не заменяет body и статус |
| HTTP | Неизвестный/unpublished slug | G-META | Выполнено частично | View использовал `get_object_or_404(published_news())` | Поведение сохранено и покрыто тестом вместе с custom 404 | Выполнено | P0 | автотест | Нет |
| Перелинковка | Битые внутренние ссылки | G-LINKS, XLSX-G | Не выполнено | Автоматической проверки не было | Локальный серверный обход 30 demo URL: failures `[]`, redirects `[]` | Выполнено | P1 | повторить crawler на production/export | Проверить полный production archive внешним crawler после деплоя |
| Перелинковка | Crawlable links/анкоры | G-LINKS, XLSX-R, XLSX-G | Частично | Основные ссылки были обычными `<a href>` | Сохранены серверные ссылки; breadcrumbs усилили путь вверх | Выполнено | P2 | HTML без JS | Редакционно улучшать контекстные ссылки в новых статьях |
| Архитектура | Глубина страниц | G-LINKS, XLSX-G | Выполнено | Новость доступна с главной/рубрики, URL `/news/slug/` | Структура не усложнялась; sitemap дополняет обнаружение | Выполнено | P2 | crawler click depth | На полном архиве проверить orphan pages |
| Пагинация | Canonical и навигация | G-CANON | Не выполнено | Canonical отсутствовал | Каждая страница рубрики/тега self-canonical с одним `page=N`; prev/next — обычные ссылки | Выполнено | P1 | автотест страницы 2 | Проверить крайние/невалидные page параметры на production |
| Таксономия | Активные рубрики и теги | G-SITEMAP | Частично | Публичные views фильтровали active, sitemap отсутствовала | В sitemap только active сущности с хотя бы одной текущей опубликованной новостью | Выполнено | P1 | XML + тест | Редактору закрывать пустые/устаревшие таксономии |
| Поиск | Индексация результатов | G-META, G-CANON, XLSX-G | Не выполнено | Поиск был индексируемым и создавал query URL | `noindex,follow`, X-Robots-Tag, canonical `/search/`; robots разрешает обход, чтобы noindex был виден | Выполнено | P0 | автотест | Проверить уже попавшие в индекс URL через GSC/Яндекс |
| Новости | Даты публикации/обновления | G-ARTICLE, G-SITEMAP | Частично | `<time>` был; schema/sitemap dates отсутствовали | ISO dates в HTML/OG/JSON-LD, sitemap `lastmod=updated_at` | Выполнено | P1 | HTML/XML/schema test | Редактору не менять `date_start` без причины |
| Новости | Автор | G-ARTICLE | Частично | Модель не имеет author; UI честно указывает «Ставрополь+ / Редакция» | Schema использует Organization «Ставрополь+», персональный автор не выдуман | Частично | P2 | JSON-LD | Отдельно решить, нужна ли модель/byline редактора и публичные профили |
| AI-материалы | Первоисточник | Редакционная прозрачность, G-ARTICLE | Выполнено | Этап 2 уже выводил source name/URL/date | Атрибуция сохранена; JSON-LD добавляет `isBasedOn` для AI draft после ручной публикации | Выполнено | P0 | тест AI pipeline + schema inspection | Редактор обязан проверять источник до публикации |
| Публикация | Черновики/будущие/завершившиеся | G-SITEMAP | Частично | Views исключали их; sitemap отсутствовала | Обе sitemap используют те же временные условия; тест покрывает три исключения | Выполнено | P0 | автотест | Убедиться в синхронном времени production |
| URL | Уникальность и query | G-CANON | Частично | Model slugs unique, но legacy/query создавали дубли | Unique slugs сохранены, legacy 301, whitelist query для canonical | Выполнено | P0 | автотест/crawler | Проверить UTM/старые URL в логах |
| Rendering | Контент без JavaScript | G-LINKS | Частично | Текст/ссылки server-rendered; часть изображений использовала `data-deferred-src` | Карточки используют native `src`; весь основной контент и навигация доступны без JS | Выполнено | P1 | отключить JS/curl HTML | Проверить меню: дополнительный drawer интерактивен, но основные header/footer links доступны |
| Бренд | Favicon | Google Search appearance, XLSX-G | Не выполнено | В `<head>` favicon отсутствовал | Подключён существующий официальный SVG 64×64 | Выполнено | P2 | HTML/браузер/GSC | После деплоя запросить переобход главной |
| Инструменты | PageSpeed | WEB-VITALS, XLSX-R, XLSX-G | Не выполнено | Официальный API: HTTP/JSON 429 `RESOURCE_EXHAUSTED`; значения не получены | Подготовлен точный runbook, вымышленных чисел нет | Требует проверки на продакшене | P1 | pagespeed.web.dev | Владелец/разработчик выполняет после деплоя |
| Google | Search Console | G-SITEMAP, G-RECRAWL | Не выполнено | Доступ к аккаунту не предоставлен | Подготовлена инструкция verify/sitemaps/inspection/indexing/CWV | Требует доступа владельца | P0 | GSC | Выполнить список из `docs/SEO_INDEXING.md` |
| Яндекс | Вебмастер | Y-START, Y-RIGHTS, Y-SITEMAP, Y-REINDEX | Не выполнено | Доступ к аккаунту не предоставлен | Подготовлена инструкция verify/robots/sitemaps/reindex/excluded URLs | Требует доступа владельца | P0 | Яндекс Вебмастер | Выполнить список из runbook |

## Полнота применения Excel-чек-листов

### `SEO_чек-лист_sad-restoran.ru.xlsx`

Лист «Чек-лист SEO» сопоставлен полностью:

| Исходный пункт | Решение для новостного портала | Ссылка на матрицу/статус |
|---|---|---|
| robots.txt, sitemap.xml, canonical, Title, Description, один H1, H2–H3 | Применимо | Строки «Индексация», «Метаданные», «Структура» |
| Главная ресторана | Неприменимо | Ресторанный коммерческий интент не переносился |
| Банкетный зал | Неприменимо | Нет такой услуги |
| Корпоративы | Неприменимо | Нет такой услуги |
| Свадьбы | Неприменимо | Нет такой услуги |
| Дни рождения / юбилеи | Неприменимо | Нет такой услуги |
| Меню | Неприменимо | Нет каталога блюд |
| Морепродукты | Неприменимо | Нет каталога блюд |
| Завтраки | Неприменимо | Нет ресторанного меню |
| Доставка | Неприменимо | Нет корзины/доставки |
| Афиша | Неприменимо | Отдельной событийной модели нет; не создавалась ради чужого чек-листа |
| NAP | Неприменимо | Юридический адрес/телефон не подтверждены и не выдумывались |
| Яндекс Бизнес / 2ГИС | Неприменимо | LocalBusiness-продвижение ресторана не относится к порталу |
| Restaurant / LocalBusiness | Неприменимо | Заменено честным `NewsMediaOrganization` |
| Event | Неприменимо | Событийных landing pages/модели нет |
| BreadcrumbList | Применимо | Выполнено |
| ALT и имена файлов | Применимо | Выполнено/частично для legacy filenames |
| WebP/AVIF + lazy-load | Применимо | Частично по WebP, выполнено по native lazy/eager LCP |
| Core Web Vitals | Применимо | Требует проверки на продакшене |
| Тематические связи | Применимо по смыслу | Выполнено базовой навигацией/breadcrumbs; контекстные ссылки — редакционный процесс |
| Бронирование | Неприменимо | Не создавалось |
| Яндекс Метрика | Частично | Аналитический аккаунт/счётчик требуют отдельного решения владельца, P2 |
| FAQ ресторана | Неприменимо | Не создавалось |

Лист «SEO по страницам»: все 18 ресторанных посадочных (`/`, `/o-nas/`,
`/menu/`, seafood, breakfast, drinks, banquet, corporate, wedding, birthday,
delivery, events, promotions, bonus program, gallery, reviews, contacts,
snacks/salads) классифицированы как **Неприменимо** в роли карты страниц.
Из структуры листа перенесён только принцип page-specific title/H1/description и
breadcrumbs; коммерческие ключи и предлагаемые URL не переносились.

Лист «Семантическое ядро»: все 24 ресторанных кластера (ресторан, панорамный
ресторан, меню, банкет, свадьба, день рождения, корпоратив, конференции,
морепродукты, устрицы, завтраки, доставка, закуски, горячие блюда, пицца,
десерты, коктейли, афиша, новогодний корпоратив, акции, отзывы, контакты,
семейный ресторан, романтический ужин) — **Неприменимо**. Семантическое ядро
новостного портала требует отдельного редакционного исследования, а не замены
слов в ресторанном шаблоне.

Лист «Рекомендации»: пункты 1–9 и 11–12 ресторанные — **Неприменимо**;
пункт 10 адаптирован к NewsMediaOrganization/Breadcrumb; 13 — к ALT/WebP;
14 — к Web Vitals; 15 — к новостной перелинковке; 16 — **Частично** как
редакционный контент-план, без генерации тем; 17 — **Требует доступа владельца**
для аналитики.

### `Изменённый чек-лист.xlsx`

| Все 18 исходных пунктов | Статус применения |
|---|---|
| Sitemap | Выполнено |
| robots.txt | Выполнено |
| Favicon | Выполнено существующим SVG; совет «только .ico» не применялся как устаревшее ограничение |
| Скорость | Требует проверки на продакшене |
| Поиск по сайту | Функция уже была; SEO-индексация поиска исправлена |
| Фильтрация | Неприменимо: товарных фильтров нет |
| 301 www | Выполнено в приложении, требуется продублировать/проверить в Nginx |
| 301 index.html/index.php | Выполнено |
| Description | Выполнено |
| Title | Выполнено |
| Изображения | Частично: ALT/lazy/dimensions улучшены, legacy media требуют инвентаризации |
| Наличие новостей | Выполнено архитектурой проекта; draft-only AI workflow сохранён |
| Вложенность | Выполнено для основных типов URL; полный архив проверить crawler |
| Schema.org/Organization | Выполнено как `NewsMediaOrganization` |
| Canonical | Выполнено |
| Open Graph | Выполнено |
| Битые ссылки и 404 | Выполнено локально: 30 URL, ошибок нет; production crawl ещё нужен |
| Анкорные ссылки | Выполнено базово; качество контекстных анкоров остаётся редакционной задачей |

## PageSpeed baseline и повторная проверка

22.09.2026 выполнена попытка официального PageSpeed Insights API для
`https://stavplus.ru/`, mobile, по категориям Performance, Accessibility, Best
Practices и SEO. API вернул `429 RESOURCE_EXHAUSTED` с сообщением о дневной
квоте. Поэтому показатели Performance/Accessibility/Best Practices/SEO, LCP,
CLS и INP **не получены и не придуманы**.

Локальный Lighthouse CLI в окружении отсутствовал. Chrome установлен, но
установка нового npm-инструмента не выполнялась только ради искусственного
прогона на demo SQLite: такой результат не равен production. Точный порядок
трёх URL × mobile/desktop и правила фиксации медианы приведены в
[`docs/SEO_INDEXING.md`](../SEO_INDEXING.md).

## Проверки и доказательства

- исходный baseline на SHA `3ea19ea`: `92` теста, `OK`;
- целевые SEO-тесты: `12`, `OK`;
- полный итоговый набор: `104` теста, `OK`;
- локальный обход server-rendered demo: `30` URL, failures `[]`, redirects `[]`;
- `python manage.py check`: успешно, только существующее предупреждение
  `ckeditor.W001`;
- `python manage.py makemigrations --check --dry-run`: `No changes detected`;
- `ruff check .`: `All checks passed!`;
- `git diff --check`: успешно, вывода нет;
- миграции БД для SEO не создавались.

Предупреждение CKEditor не скрывалось: проект использует неподдерживаемый
CKEditor 4.22.1, его замена остаётся отдельной задачей.

## Риски и ручные действия

1. **P0 — деплой отсутствует.** Публичные robots/sitemap по-прежнему 404 до
   разрешённого merge/deploy.
2. **P0 — зеркала.** Проверить один серверный `301` HTTP→HTTPS и `www`→без www;
   после завершения тестирования добавить постраничный `new`→main.
3. **P0 — доступ владельца.** Подтвердить права, отправить обе sitemap и
   проверить исключённые URL в Google Search Console и Яндекс Вебмастере.
4. **P1 — PageSpeed/CrUX.** Снять mobile/desktop для главной, рубрики и новости
   после деплоя; локальные результаты не выдавать за production.
5. **P1 — structured data.** Проверить реальные deployed URLs в Rich Results
   Test; наличие разметки не гарантирует расширенный результат.
6. **P1 — архив.** Выполнить полный production crawl для orphan/broken links,
   тяжёлых JPG и некорректной иерархии H2/H3.
7. **P2 — авторы.** Решить отдельно, нужна ли модель персональных byline; сейчас
   честно указана организация, а не вымышленный журналист.

## Rollback

Изменений данных и миграций нет. Аварийная точка отката —
`3ea19ea209969982e260b6a2327266f84c423a2d`. После возврата к ней и перезапуска
процесса исчезнут robots, sitemap, canonical, JSON-LD и новые redirect rules,
но новости/рубрики/теги не изменятся. Перед откатом сохранить логи и причину;
после — проверить `/`, одну новость, `/admin/`, статус неизвестного URL и
отсутствие redirect loop. Действия на production допускаются только по
отдельному явному разрешению.
