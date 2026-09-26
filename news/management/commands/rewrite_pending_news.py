from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.ai_news.openrouter import OpenRouterError
from news.ai_news.pipeline import (
    RewriteClaimError,
    assert_pipeline_enabled,
    configured_client,
    recover_stale_rewrite_jobs,
    rewrite_item,
)
from news.models import ImportedNewsItem


class Command(BaseCommand):
    help = 'Rewrite pending imported items through OpenRouter and create News drafts only.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--item-id', type=int)
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List pending item IDs without calling OpenRouter or changing the database.',
        )

    def handle(self, *args, **options):
        try:
            assert_pipeline_enabled()
        except OpenRouterError as error:
            raise CommandError(str(error)) from error
        if options['limit'] < 1:
            raise CommandError('--limit must be greater than zero.')

        queryset = ImportedNewsItem.objects.filter(
            status=ImportedNewsItem.ProcessingStatus.PENDING
        ).order_by('fetched_at', 'pk')
        if options['item_id']:
            queryset = queryset.filter(pk=options['item_id'])
        items = list(queryset[: options['limit']])
        if options['dry_run']:
            self.stdout.write(f"DRY RUN: pending item IDs: {[item.pk for item in items]}")
            return
        try:
            client = configured_client()
        except OpenRouterError as error:
            raise CommandError(str(error)) from error
        stale_before = timezone.now() - timedelta(
            minutes=settings.AI_NEWS_PROCESSING_TIMEOUT_MINUTES
        )
        recovered = recover_stale_rewrite_jobs(stale_before=stale_before)
        if recovered:
            self.stderr.write(f'Marked stale processing jobs as failed: {recovered}')

        succeeded = 0
        failed = 0
        for item in items:
            try:
                rewrite_item(item, client=client)
            except RewriteClaimError:
                continue
            except Exception as error:
                failed += 1
                self.stderr.write(f'Item {item.pk} failed: {type(error).__name__}')
            else:
                succeeded += 1
        self.stdout.write(self.style.SUCCESS(f'Rewritten={succeeded} failed={failed}'))
