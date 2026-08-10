"""Import the prepared local editorial content without duplicate records."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import Category, News, Tag


FIXTURE_PATH = Path(__file__).resolve().parents[2] / 'fixtures' / 'local_demo_content.json'

# The starter content remains useful immediately after a clean deployment: each
# imported material gets a small, reusable topic set. Editors can then add or
# remove tags in the admin without a later import replacing their choices.
DEFAULT_TAGS_BY_CATEGORY = {
    'obshchestvo': ('Ставрополь', 'Городская среда'),
    'politika': ('Региональная политика', 'Муниципалитеты'),
    'ekonomika': ('Экономика края', 'Предпринимательство'),
    'kultura': ('Культура', 'События'),
    'sport': ('Спорт', 'Здоровый образ жизни'),
    'nauka': ('Наука', 'Образование'),
    'proisshestviya': ('Безопасность', 'Происшествия'),
}


class Command(BaseCommand):
    help = 'Imports the prepared local categories and demo news by stable slug.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate the import and roll back every database change.',
        )

    def handle(self, *args, **options):
        try:
            records = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f'Could not read local demo fixture: {error}') from error

        category_records = [record for record in records if record['model'] == 'news.category']
        news_records = [record for record in records if record['model'] == 'news.news']
        categories_by_source_id = {}
        created_categories = updated_categories = created_news = updated_news = 0

        with transaction.atomic():
            for record in category_records:
                fields = record['fields']
                category = Category.objects.filter(slug=fields['slug']).first()
                if category is None:
                    category = Category.objects.filter(name=fields['name']).first()

                created = category is None
                if created:
                    category = Category(slug=fields['slug'])
                category.name = fields['name']
                category.description = fields['description']
                category.icon = fields['icon']
                category.order = fields['order']
                category.is_active = fields['is_active']
                category.save()
                categories_by_source_id[record['pk']] = category
                if created:
                    created_categories += 1
                else:
                    updated_categories += 1

            for record in news_records:
                fields = record['fields']
                category = categories_by_source_id.get(fields['category'])
                if fields['category'] is not None and category is None:
                    raise CommandError(f"Category for news '{fields['slug']}' was not imported.")

                publication_time = parse_datetime(fields['date_start']) if fields['date_start'] else None
                expiration_time = parse_datetime(fields['date_end']) if fields['date_end'] else None
                if fields['date_start'] and publication_time is None:
                    raise CommandError(
                        f"Invalid publication date for news '{fields['slug']}'."
                    )
                if fields['date_end'] and expiration_time is None:
                    raise CommandError(
                        f"Invalid expiration date for news '{fields['slug']}'."
                    )

                if publication_time and timezone.is_naive(publication_time):
                    publication_time = timezone.make_aware(publication_time)
                if expiration_time and timezone.is_naive(expiration_time):
                    expiration_time = timezone.make_aware(expiration_time)
                if not fields['is_published']:
                    editorial_status = News.EditorialStatus.DRAFT
                elif publication_time and publication_time > timezone.now():
                    editorial_status = News.EditorialStatus.SCHEDULED
                else:
                    editorial_status = News.EditorialStatus.PUBLISHED

                defaults = {
                    'title': fields['title'],
                    'content': fields['content'],
                    'excerpt': fields['excerpt'],
                    'category': category,
                    'main_photo': fields['main_photo'] or None,
                    'is_published': fields['is_published'],
                    'editorial_status': editorial_status,
                    'is_featured': fields.get('is_featured', False),
                    'date_start': publication_time,
                    'date_end': expiration_time,
                    'meta_title': fields['meta_title'],
                    'meta_description': fields['meta_description'],
                    'meta_keywords': fields['meta_keywords'],
                    'views': fields['views'],
                }
                news, created = News.objects.update_or_create(
                    slug=fields['slug'], defaults=defaults
                )
                for tag_name in DEFAULT_TAGS_BY_CATEGORY.get(category.slug if category else '', ()):
                    tag, _ = Tag.objects.get_or_create(name=tag_name)
                    news.tags.add(tag)
                if created:
                    created_news += 1
                else:
                    updated_news += 1

            if options['dry_run']:
                transaction.set_rollback(True)

        mode = 'validated and rolled back' if options['dry_run'] else 'imported'
        self.stdout.write(self.style.SUCCESS(
            f'Local demo content {mode}: '
            f'categories +{created_categories}/~{updated_categories}, '
            f'news +{created_news}/~{updated_news}.'
        ))
