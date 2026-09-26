# AI News Pipeline

Безопасный конвейер подготовки внешних новостей для обязательной редакторской
проверки. Версия 1 не публикует AI-материалы автоматически и не использует
Celery.

## Схема

```text
NewsSource allowlist
  → robots.txt + rate interval
  → RSS/Atom fetch (до 2 MiB)
  → plain-text normalization + input limit
  → URL/SHA-256 deduplication
  → fact candidates
  → OpenRouter JSON Schema
  → application validation + grounding warnings
  → HTML sanitization
  → News(editorial_status=DRAFT, is_published=False)
  → редакторская проверка в Django Admin
  → только ручное действие публикации
```

Команда не загружает HTML страницы статьи. В первой версии поддержаны RSS и
Atom. Тип API зарезервирован в модели, но требует отдельного адаптера. Это
уменьшает юридические риски, нагрузку на сайты и площадь атаки HTML-скрейпинга.

## Безопасные defaults

```dotenv
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_FALLBACK_MODEL=
OPENROUTER_TIMEOUT_SECONDS=30
OPENROUTER_MAX_RETRIES=2
OPENROUTER_MAX_INPUT_CHARS=12000
AI_NEWS_PROCESSING_TIMEOUT_MINUTES=30
AI_NEWS_ENABLED=false
AUTO_PUBLISH_AI_NEWS=false
```

- Ключ хранится только в окружении или deployment secrets.
- Пустая модель не позволяет случайно вызвать API.
- `AI_NEWS_ENABLED=false` отключает обе команды.
- Версия 1 намеренно прекращает работу, если
  `AUTO_PUBLISH_AI_NEWS=true`. Значение не является скрытым способом обойти
  редактора.
- Модель и fallback должны быть выбраны только после проверки поддержки
  `structured_outputs` у конкретного endpoint/provider.

OpenRouter вызывается через
`https://openrouter.ai/api/v1/chat/completions`. Запрос содержит
`response_format.type=json_schema`, `strict=true` и
`provider.require_parameters=true`. Последний параметр запрещает маршрутизацию
к endpoint, который не объявляет требуемые параметры. Поддержка может меняться,
поэтому перед сменой модели нужно повторно проверить её страницу и выполнить
mock/staging-тест. Документация:

- <https://openrouter.ai/docs/quickstart>
- <https://openrouter.ai/docs/guides/features/structured-outputs>

## Источники и allowlist

Миграция не создаёт ни одного разрешённого источника. Источник попадает в
обработку только при одновременном выполнении условий:

1. `is_active=true`;
2. `editorial_approved=true`;
3. `legal_approved=true`;
4. заполнены даты проверки условий использования и `robots.txt`;
5. URL ленты и URL материала относятся к `allowed_domains`;
6. истёк индивидуальный `min_request_interval_minutes`;
7. текущий `robots.txt` разрешает запрос ленты нашему User-Agent.

Блокировки, CAPTCHA и ограничения доступа не обходятся. URL с credentials,
localhost, `.local`, приватными или зарезервированными IP запрещены. HTTP(S)
transport отключает environment proxy и подключается к уже проверенному
результату DNS, поэтому повторное DNS-разрешение не может перенаправить запрос
во внутреннюю сеть. Каждый redirect проходит ту же проверку. RSS/Atom с DTD или
entity declarations отклоняется. Один URL и одинаковый SHA-256
нормализованного материала повторно не обрабатываются.

До включения юридическое и редакционное согласование требуется для каждой
конкретной ленты, включая:

- ТАСС, Интерфакс, РИА Новости и другие федеральные СМИ;
- федеральные ведомства и их региональные управления;
- портал органов власти Ставропольского края и муниципальные сайты;
- МЧС, МВД, прокуратуру и иные официальные региональные источники;
- региональные и муниципальные СМИ;
- любые коммерческие API, агрегаторы и платные ленты.

Наличие публичного RSS само по себе не означает разрешение на рерайт или
публикацию. Для каждого источника отдельно фиксируются допустимый объём
использования, атрибуция, частота, robots.txt и условия лицензии.

## Защита от prompt injection

Текст источника передаётся как JSON-поле `untrusted_source_data` в отдельном
user message. System message прямо запрещает выполнять инструкции из статьи.
Перед моделью выделяются кандидаты фактов; результат может ссылаться только на
их `fact_id` и исходный URL. Неизвестные fact ID отклоняются.

Модели запрещено придумывать цитаты, числа, даты, фамилии, организации,
должности и причинные связи. После ответа приложение дополнительно отмечает:

- числа, которых не было в источнике;
- цитаты, не найденные дословно;
- пустые или невалидные обязательные поля;
- неизвестные факты и URL;
- предупреждения самой модели.

При предупреждениях запись получает `needs_review`; созданная `News` всё равно
остаётся DRAFT. Generated HTML проходит allowlist-sanitization: удаляются
scripts, iframes, handlers, изображения и небезопасные ссылки.

## Prompt и результат

- prompt version: `stavplus-ai-news-v1`;
- обязательные поля: `title`, `excerpt`, `content`, `category_suggestion`,
  `tags`, `meta_title`, `meta_description`, `source_facts`, `warnings`;
- категория и теги не создаются моделью: используются только уже существующие
  активные записи с совпадающими именами;
- публичная страница AI-материала показывает источник, оригинальный URL, дату и
  предупреждает, что текст не является собственным репортажем.

## Запуск

Сначала применить миграцию и создать `NewsSource` через Admin. До согласования
все флаги источника должны оставаться выключенными.

Безопасный dry-run одного согласованного источника:

```bash
AI_NEWS_ENABLED=true AUTO_PUBLISH_AI_NEWS=false \
python manage.py ingest_external_news \
  --dry-run \
  --source "Название согласованного источника" \
  --limit 5
```

Dry-run обращается к RSS/Atom и robots.txt, но не пишет записи и не вызывает
OpenRouter. После проверки отчёта:

```bash
python manage.py ingest_external_news --source "Название согласованного источника" --limit 10
python manage.py rewrite_pending_news --dry-run --limit 10
python manage.py rewrite_pending_news --limit 10
```

Для последних двух команд окружение должно содержать реальный ключ и
проверенную модель. Запуск из cron/PM2 не настраивается этой веткой. Перед
автоматизацией редакция должна подтвердить источник, расписание и бюджет.

## Django Admin

Редактор видит источник, оригинальный URL, состояние, модель, prompt version,
ошибку, предупреждения, токены, стоимость и созданный черновик. Доступны два
явных действия:

- «Повторить AI-рерайт»;
- «Отправить созданный черновик в публикацию».

Публикация AI-новости проходит через централизованную policy независимо от
того, запущена она из списка импортов или общим действием в списке новостей.
Policy разрешает только `draft_ready` без предупреждений, проверяет canonical
evidence и обязательные поля, блокирует строки на время короткой транзакции и
создаёт audit event с именем редактора. Прямой model save, bulk update и смена
статуса через форму не обходят policy. Снятие с публикации также синхронно
возвращает импорт в `draft_ready` или `needs_review` и пишет audit event.
Обычный редакционный workflow DRAFT/SCHEDULED/PUBLISHED сохраняется.

## Ошибки и retries

- timeout задаётся `OPENROUTER_TIMEOUT_SECONDS`;
- retry выполняется только для timeout, network error, HTTP 429 и 5xx;
- `OPENROUTER_MAX_RETRIES=2` означает до трёх запросов на модель;
- после исчерпания retries может использоваться fallback;
- 4xx, schema mismatch и invalid JSON не повторяются на той же модели;
- логи не содержат API key, полный request/response payload или текст статьи.

Worker атомарно переводит только `pending` запись в `processing` коротким
conditional update и фиксирует `rewrite_started`; только после commit вызывается
OpenRouter. Второй worker не получает claim и не делает HTTP-запрос. Результат
записывается отдельной короткой транзакцией, только если claim всё ещё актуален.
Зависший `processing` старше `AI_NEWS_PROCESSING_TIMEOUT_MINUTES` переводится в
`failed` с audit event. Повторный запуск после failure требует явного действия
редактора.

## Стоимость и стартовый лимит

Формула одного успешного запроса:

```text
input_tokens × input_price_per_token
+ output_tokens × output_price_per_token
```

Проверка публичного каталога OpenRouter 2026-09-22 показала для примера
`openai/gpt-5.6-luna` поддержку `structured_outputs` и цены `$0.20 / 1M`
input tokens и `$1.20 / 1M` output tokens. При 3 000 input и 1 000 output это
около `$0.0018` за успешный материал. Три попытки — до `$0.0054`; если также
исчерпать fallback с той же ценой — до `$0.0108`.

Это оценка, не гарантия: цена, endpoint и токенизация меняются. Фактические
`prompt_tokens`, `completion_tokens` и `usage.cost` сохраняются в
`ImportedNewsItem`.

Стартовый операционный лимит: **10 материалов в сутки**, один запуск
`rewrite_pending_news --limit 10` в сутки. Ожидаемо около `$0.018/сутки`,
верхняя оценка при retries и fallback — `$0.108/сутки`. Приложение не создаёт
cron и не препятствует оператору запустить команду повторно; перед расписанием
нужен отдельный hard budget/alert на стороне OpenRouter и подтверждение
редакции.

## Rollback

1. Остановить cron/PM2-задачу, если она была создана отдельно.
2. Установить `AI_NEWS_ENABLED=false` и `AUTO_PUBLISH_AI_NEWS=false`.
3. Не удалять импортированные записи до выгрузки audit trail.
4. Откатить код соответствующими Git-коммитами.
5. Для удаления таблиц только после backup выполнить
   `python manage.py migrate news 0008`; это удалит данные `NewsSource`,
   `ImportedNewsItem` и `AIRewriteAuditEvent`, поэтому шаг является
   destructive и требует отдельного подтверждения.
6. Созданные `News` не удаляются миграционным rollback автоматически. Их нужно
   оставить DRAFT или обработать редакционно по audit trail.

Эта ветка не выполняет deploy, `migrate` на production, настройку расписания или
публикацию материалов.
