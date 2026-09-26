from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from news.ai_news.openrouter import OpenRouterError
from news.ai_news.pipeline import assert_pipeline_enabled
from news.ai_news.sources import (
    SourceFetchError,
    content_digest,
    extract_fact_candidates,
    fetch_bytes,
    normalize_entry,
    parse_feed,
    robots_allows,
    validate_source_url,
)
from news.models import AIRewriteAuditEvent, ImportedNewsItem, NewsSource


class Command(BaseCommand):
    help = 'Load approved RSS/Atom entries into the draft-only AI news queue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and validate feeds without writing database records.',
        )
        parser.add_argument('--source', help='Process one source by its exact name.')
        parser.add_argument('--limit', type=int, default=50, help='Maximum entries per source.')

    def handle(self, *args, **options):
        try:
            assert_pipeline_enabled()
        except OpenRouterError as error:
            raise CommandError(str(error)) from error
        if options['limit'] < 1:
            raise CommandError('--limit must be greater than zero.')

        sources = NewsSource.objects.all()
        if options['source']:
            sources = sources.filter(name=options['source'])
        if not sources.exists():
            self.stdout.write('No configured sources matched.')
            return

        totals = {'created': 0, 'duplicate_url': 0, 'duplicate_hash': 0, 'skipped': 0}
        for source in sources:
            counts = self._ingest_source(source, dry_run=options['dry_run'], limit=options['limit'])
            for name, value in counts.items():
                totals[name] += value
        mode = 'DRY RUN' if options['dry_run'] else 'APPLY'
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: created={totals['created']} duplicate_url={totals['duplicate_url']} "
                f"duplicate_hash={totals['duplicate_hash']} skipped={totals['skipped']}"
            )
        )

    def _ingest_source(self, source, *, dry_run, limit):
        counts = {'created': 0, 'duplicate_url': 0, 'duplicate_hash': 0, 'skipped': 0}
        if not source.is_approved_for_ingestion:
            self.stdout.write(self.style.WARNING(f'Skipped unapproved source: {source.name}'))
            counts['skipped'] += 1
            return counts
        if source.source_type not in {NewsSource.SourceType.RSS, NewsSource.SourceType.ATOM}:
            self.stdout.write(self.style.WARNING(f'Skipped source without an API adapter: {source.name}'))
            counts['skipped'] += 1
            return counts
        now = timezone.now()
        if source.last_fetched_at and now < source.last_fetched_at + timedelta(
            minutes=source.min_request_interval_minutes
        ):
            self.stdout.write(self.style.WARNING(f'Rate limit interval not elapsed: {source.name}'))
            counts['skipped'] += 1
            return counts

        domains = source.allowed_domain_list()
        try:
            validate_source_url(source.feed_url, domains)
            if not robots_allows(
                source.feed_url,
                allowed_domains=domains,
                timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
            ):
                raise SourceFetchError('robots.txt disallows this feed URL.')
            payload = fetch_bytes(
                source.feed_url,
                allowed_domains=domains,
                timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
            )
            entries = parse_feed(payload)[:limit]
        except Exception as error:
            safe_message = str(error)[:300] if isinstance(error, SourceFetchError) else type(error).__name__
            raise CommandError(f'Could not load approved source {source.name}: {safe_message}') from error

        for entry in entries:
            try:
                validate_source_url(entry.url, domains)
            except SourceFetchError:
                counts['skipped'] += 1
                continue
            title, text = normalize_entry(entry, max_chars=settings.OPENROUTER_MAX_INPUT_CHARS)
            if not title or len(text) < 50:
                counts['skipped'] += 1
                continue
            digest = content_digest(title, text)
            if ImportedNewsItem.objects.filter(source_url=entry.url).exists():
                counts['duplicate_url'] += 1
                continue
            if ImportedNewsItem.objects.filter(content_hash=digest).exists():
                counts['duplicate_hash'] += 1
                continue
            facts = extract_fact_candidates(text, entry.url)
            if dry_run:
                counts['created'] += 1
                continue
            try:
                with transaction.atomic():
                    item = ImportedNewsItem.objects.create(
                        source=source,
                        source_url=entry.url,
                        source_name=source.name,
                        source_title=title,
                        source_published_at=entry.published_at,
                        fetched_at=now,
                        normalized_text=text,
                        content_hash=digest,
                        extracted_facts=facts,
                        status=(
                            ImportedNewsItem.ProcessingStatus.PENDING
                            if facts
                            else ImportedNewsItem.ProcessingStatus.NEEDS_REVIEW
                        ),
                        warnings=[] if facts else ['Не удалось выделить проверяемые факты.'],
                    )
                    AIRewriteAuditEvent.objects.create(
                        item=item,
                        event_type='source_ingested',
                        message='Материал загружен из одобренной ленты и ожидает рерайта.',
                        details={'facts_count': len(facts)},
                    )
            except IntegrityError:
                counts['duplicate_url'] += 1
                continue
            counts['created'] += 1

        if not dry_run:
            source.last_fetched_at = now
            source.save(update_fields=('last_fetched_at', 'updated_at'))
        return counts
