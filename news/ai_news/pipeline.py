from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from news.models import AIRewriteAuditEvent, Category, ImportedNewsItem, News, Tag

from .openrouter import PROMPT_VERSION, OpenRouterClient, OpenRouterError, StructuredOutputError
from .sanitization import normalize_external_text, sanitize_generated_html


STALE_REWRITE_MESSAGE = 'Предыдущая попытка рерайта прервана или превысила допустимое время.'


class RewriteClaimError(OpenRouterError):
    """The item could not be claimed, or this worker no longer owns its claim."""


def assert_pipeline_enabled() -> None:
    if settings.AUTO_PUBLISH_AI_NEWS:
        raise OpenRouterError(
            'AUTO_PUBLISH_AI_NEWS=true is not supported in version 1. '
            'AI drafts require manual publication.'
        )
    if not settings.AI_NEWS_ENABLED:
        raise OpenRouterError('AI_NEWS_ENABLED is false; the pipeline is disabled.')


def configured_client() -> OpenRouterClient:
    return OpenRouterClient(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        fallback_model=settings.OPENROUTER_FALLBACK_MODEL,
        timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        max_retries=settings.OPENROUTER_MAX_RETRIES,
        max_input_chars=settings.OPENROUTER_MAX_INPUT_CHARS,
    )


def rewrite_item(item: ImportedNewsItem, *, client: OpenRouterClient) -> ImportedNewsItem:
    if not claim_rewrite_item(item):
        raise RewriteClaimError('Imported news item is not pending and was not claimed.')
    claim_started_at = item.last_attempted_at

    try:
        if not item.source_url:
            raise OpenRouterError('An imported item without a source URL cannot be rewritten.')
        result = client.rewrite(
            source_name=item.source_name,
            source_url=item.source_url,
            source_published_at=item.source_published_at,
            source_title=item.source_title,
            source_text=item.normalized_text,
            fact_candidates=item.extracted_facts,
        )
        _store_draft(item, result, claim_started_at=claim_started_at)
    except Exception as error:
        _mark_claim_failed(item.pk, claim_started_at=claim_started_at, error=error)
        raise
    item.refresh_from_db()
    return item


def claim_rewrite_item(item: ImportedNewsItem) -> bool:
    """Atomically move one pending item to processing before any provider call."""
    claimed_at = timezone.now()
    with transaction.atomic():
        claimed = ImportedNewsItem.objects.filter(
            pk=item.pk,
            status=ImportedNewsItem.ProcessingStatus.PENDING,
        ).update(
            status=ImportedNewsItem.ProcessingStatus.PROCESSING,
            last_attempted_at=claimed_at,
            retry_count=F('retry_count') + 1,
            error_message='',
            updated_at=claimed_at,
        )
        if not claimed:
            return False
        item.refresh_from_db()
        AIRewriteAuditEvent.objects.create(
            item=item,
            event_type='rewrite_started',
            message='Запущен AI-рерайт с обязательным structured output.',
            details={'attempt': item.retry_count},
        )
    return True


def recover_stale_rewrite_jobs(*, stale_before) -> int:
    """Fail abandoned processing claims so an editor can explicitly retry them."""
    stale_filter = Q(last_attempted_at__lt=stale_before) | Q(last_attempted_at__isnull=True)
    item_ids = list(
        ImportedNewsItem.objects.filter(
            Q(status=ImportedNewsItem.ProcessingStatus.PROCESSING) & stale_filter
        ).values_list('pk', flat=True)
    )
    recovered = 0
    for item_id in item_ids:
        with transaction.atomic():
            updated = ImportedNewsItem.objects.filter(
                Q(pk=item_id, status=ImportedNewsItem.ProcessingStatus.PROCESSING)
                & stale_filter
            ).update(
                status=ImportedNewsItem.ProcessingStatus.FAILED,
                error_message=STALE_REWRITE_MESSAGE,
                updated_at=timezone.now(),
            )
            if not updated:
                continue
            AIRewriteAuditEvent.objects.create(
                item_id=item_id,
                event_type='rewrite_stale',
                message=STALE_REWRITE_MESSAGE,
            )
            recovered += 1
    return recovered


def _store_draft(item, result, *, claim_started_at) -> None:
    data = result.data
    title = normalize_external_text(data['title'], max_chars=255)
    excerpt = normalize_external_text(data['excerpt'], max_chars=500)
    content = sanitize_generated_html(data['content'])
    meta_title = normalize_external_text(data['meta_title'], max_chars=255)
    meta_description = normalize_external_text(data['meta_description'], max_chars=255)
    if not title or not excerpt or len(normalize_external_text(content, max_chars=30000)) < 50:
        raise StructuredOutputError('Sanitized draft is missing required editorial content.')

    category = None
    category_name = data['category_suggestion'].strip()
    if category_name:
        category = Category.objects.filter(name__iexact=category_name, is_active=True).first()

    tags = []
    for tag_name in data['tags']:
        tag = Tag.objects.filter(name__iexact=tag_name.strip(), is_active=True).first()
        if tag and tag not in tags:
            tags.append(tag)

    with transaction.atomic():
        item = ImportedNewsItem.objects.select_for_update().get(pk=item.pk)
        if (
            item.status != ImportedNewsItem.ProcessingStatus.PROCESSING
            or item.last_attempted_at != claim_started_at
        ):
            raise RewriteClaimError('Rewrite claim is no longer active; result was discarded.')
        if item.created_news_id:
            news = News.objects.select_for_update().get(pk=item.created_news_id)
            news.title = title
            news.excerpt = excerpt
            news.content = content
            news.category = category
            news.meta_title = meta_title
            news.meta_description = meta_description
            news.editorial_status = News.EditorialStatus.DRAFT
            news.is_published = False
            news.is_featured = False
            news.save()
        else:
            news = News.objects.create(
                title=title,
                excerpt=excerpt,
                content=content,
                category=category,
                meta_title=meta_title,
                meta_description=meta_description,
                editorial_status=News.EditorialStatus.DRAFT,
                is_published=False,
                is_featured=False,
                date_start=item.source_published_at or timezone.now(),
            )
        news.tags.set(tags)
        item.created_news = news
        item.status = (
            ImportedNewsItem.ProcessingStatus.NEEDS_REVIEW
            if data['warnings']
            else ImportedNewsItem.ProcessingStatus.DRAFT_READY
        )
        item.rewrite_model = result.model
        item.prompt_version = PROMPT_VERSION
        item.provider_response_id = result.response_id
        item.source_facts = data['source_facts']
        item.warnings = data['warnings']
        item.error_message = ''
        item.input_tokens = result.input_tokens
        item.output_tokens = result.output_tokens
        item.provider_cost_usd = result.cost_usd
        item.save(
            update_fields=(
                'created_news',
                'status',
                'rewrite_model',
                'prompt_version',
                'provider_response_id',
                'source_facts',
                'warnings',
                'error_message',
                'input_tokens',
                'output_tokens',
                'provider_cost_usd',
                'updated_at',
            )
        )
        AIRewriteAuditEvent.objects.create(
            item=item,
            event_type='draft_created' if not data['warnings'] else 'manual_review_required',
            message=(
                'Создан или обновлён только редакционный черновик. Автопубликация не выполнялась.'
            ),
            details={
                'news_id': news.pk,
                'model': result.model,
                'prompt_version': item.prompt_version,
                'warnings_count': len(data['warnings']),
            },
        )


def _mark_claim_failed(item_id: int, *, claim_started_at, error: Exception) -> None:
    safe_error = _safe_error_message(error)
    with transaction.atomic():
        updated = ImportedNewsItem.objects.filter(
            pk=item_id,
            status=ImportedNewsItem.ProcessingStatus.PROCESSING,
            last_attempted_at=claim_started_at,
        ).update(
            status=ImportedNewsItem.ProcessingStatus.FAILED,
            error_message=safe_error,
            updated_at=timezone.now(),
        )
        if updated:
            AIRewriteAuditEvent.objects.create(
                item_id=item_id,
                event_type='rewrite_failed',
                message=safe_error,
            )


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, OpenRouterError):
        return str(error)[:1000]
    return f'{type(error).__name__}: processing failed'[:1000]
