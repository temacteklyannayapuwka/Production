# AI News Pipeline — отчёт 2026-09-22

## Scope и база

- Репозиторий: `temacteklyannayapuwka/Production`.
- База: `origin/redesign/full-site`.
- Базовый SHA: `044245acc423072af0bf1f7c3657e97636b2a305`.
- Ветка: `feature/ai-news-pipeline`.
- Production deploy: не выполнялся.
- Push и PR: ожидают финальных проверок.

## Аудит до изменений

- `News` уже поддерживала DRAFT/SCHEDULED/PUBLISHED; `save()` делал DRAFT
  неопубликованным.
- Public views фильтровали `is_published=True`, дату начала и дату окончания.
- Django Admin имел ручные действия publish/unpublish.
- K2 importer дал проверенный шаблон dry-run, идемпотентного обновления,
  sanitized errors и rollback через backup.
- Очереди задач и Celery отсутствовали; для v1 они не требуются.
- HTTP/OpenRouter-зависимости отсутствовали; реализация использует стандартную
  библиотеку Python.
- Известное предупреждение `ckeditor.W001` существовало до этой ветки.

## Реализация

Добавлены:

- `NewsSource` — allowlist, approvals, domains, terms/robots review, rate interval;
- `ImportedNewsItem` — provenance, URL/hash dedupe, status, model/prompt,
  errors/retries, usage/cost и связь с `News`;
- `AIRewriteAuditEvent` — append-only журнал этапов и ручных действий;
- RSS/Atom parser, robots.txt check, URL allowlist и нормализация;
- OpenRouter client с timeout, bounded backoff/retries, fallback и strict JSON
  Schema;
- prompt-injection boundary, fact IDs, validation и sanitization;
- `ingest_external_news` с `--dry-run`;
- `rewrite_pending_news` с preview dry-run;
- Admin review/retry/manual publish actions;
- публичная атрибуция источника для вручную опубликованного AI-материала.

AI-материал всегда создаётся с:

```text
editorial_status = draft
is_published = false
is_featured = false
```

`AUTO_PUBLISH_AI_NEWS=true` в v1 приводит к отказу команды, а не к публикации.

## Модель и prompt

- Base URL: `https://openrouter.ai/api/v1`.
- Endpoint: `/chat/completions`.
- Prompt version: `stavplus-ai-news-v1`.
- Модель в defaults: пустая, запуск невозможен до явной настройки.
- Кандидат для редакционной оценки: `openai/gpt-5.6-luna`.
- Runtime-проверка capability: `provider.require_parameters=true` плюс
  `response_format.type=json_schema`.

## Источники

Разрешённых записей по умолчанию нет. Любой федеральный, ведомственный,
региональный или коммерческий источник требует отдельного юридического и
редакционного согласования. HTML scraping в v1 не реализован.

## Стоимость и лимит

По публичному каталогу OpenRouter, проверенному 2026-09-22, примерная стоимость
`openai/gpt-5.6-luna` при 3 000 input + 1 000 output tokens — `$0.0018` за
успешный материал. С retries/fallback верхняя расчётная оценка — `$0.0108`.
Стартовый операционный лимит — 10 материалов/сутки одним запуском; expected
`$0.018/сутки`, расчётный upper bound `$0.108/сутки`. Перед cron нужен отдельный
OpenRouter budget/alert.

## Результаты проверок

Mock-suite `news.tests_ai_news`: **21/21 passed**.

Покрыты:

- successful structured response;
- timeout, HTTP 429 и 5xx;
- invalid JSON и invalid schema;
- повторный URL и content hash;
- prompt injection в исходном тексте;
- отсутствие API key;
- создание только DRAFT;
- sanitization;
- идемпотентный повтор;
- warnings → manual review;
- только ручная публикация;
- safe defaults и отказ при auto-publish.

Полный набор на Python 3.12 / Django 6.0.6:

- `python manage.py check` — passed; одно существующее предупреждение
  `ckeditor.W001`;
- `python manage.py makemigrations --check --dry-run` — `No changes detected`;
- `python manage.py test` — **92/92 passed**;
- `ruff check .` — passed;
- `git diff --check` — passed.

## Миграции

- `news/migrations/0009_newssource_importednewsitem_airewriteauditevent_and_more.py`.
- Создаются три таблицы и индекс `(status, fetched_at)`.
- Production migration не выполнялась.

## Изменённые области

- `.env.example`, `stavplus/settings.py`;
- `news/models.py`, `news/admin.py`, `news/views.py`;
- `news/ai_news/`;
- `news/management/commands/`;
- migration `0009`;
- `news/tests_ai_news.py`;
- `templates/article.html` и source-attribution component;
- `docs/AI_NEWS_PIPELINE.md` и этот отчёт.

## Риски и нерешённые вопросы

- юридическое согласование конкретных RSS/Atom-лент;
- редакционная оценка качества модели на русскоязычных региональных новостях;
- hard daily budget/alert до создания расписания;
- политика хранения нормализованного исходного текста;
- критерии допустимых предупреждений перед ручной публикацией;
- отдельный API adapter, если будет одобрен источник без RSS/Atom;
- обновление устаревшего CKEditor — отдельная задача, не часть pipeline.

## Rollback

Сначала отключить `AI_NEWS_ENABLED`, остановить внешнее расписание и сохранить
audit trail. Затем откатить код. Миграционный rollback до `news 0008` удаляет
три новые таблицы и допускается только после backup и отдельного подтверждения.
Созданные `News` автоматически не удаляются и должны остаться DRAFT либо быть
обработаны редактором.
