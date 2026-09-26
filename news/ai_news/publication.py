from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from news.models import (
    AIRewriteAuditEvent,
    ImportedNewsItem,
    News,
    _AI_PUBLICATION_TOKEN,
)


class PublicationPolicyError(ValidationError):
    pass


def publish_ai_draft(item_id: int, *, actor: str) -> News:
    """Publish one reviewed AI draft and record the human decision atomically."""
    if settings.AUTO_PUBLISH_AI_NEWS:
        raise PublicationPolicyError(
            'AUTO_PUBLISH_AI_NEWS=true is not supported; manual publication is required.'
        )
    actor = str(actor or '').strip()[:160]
    if not actor:
        raise PublicationPolicyError('A named editorial actor is required for publication.')

    with transaction.atomic():
        item = (
            ImportedNewsItem.objects.select_for_update()
            .select_related('created_news')
            .get(pk=item_id)
        )
        if item.status != ImportedNewsItem.ProcessingStatus.DRAFT_READY:
            raise PublicationPolicyError('Only a draft-ready AI item can be published.')
        if item.warnings:
            raise PublicationPolicyError('AI drafts with warnings require review and cannot publish.')
        if not item.created_news_id:
            raise PublicationPolicyError('The imported item has no generated draft.')
        if not item.source_url or not item.source_facts:
            raise PublicationPolicyError('The AI draft is missing canonical source evidence.')

        news = News.objects.select_for_update().get(pk=item.created_news_id)
        if not news.title.strip() or not news.content.strip():
            raise PublicationPolicyError('The AI draft is missing required editorial content.')

        news.editorial_status = News.EditorialStatus.PUBLISHED
        news.is_published = True
        news.date_start = timezone.now()
        news.save(
            update_fields=('editorial_status', 'is_published', 'date_start', 'updated_at'),
            ai_publication_token=_AI_PUBLICATION_TOKEN,
        )
        item.status = ImportedNewsItem.ProcessingStatus.PUBLISHED
        item.save(update_fields=('status', 'updated_at'))
        AIRewriteAuditEvent.objects.create(
            item=item,
            event_type='published_manually',
            actor=actor,
            message='Редактор вручную отправил AI-черновик в публикацию.',
        )
        return news
