"""Convert news photos to appropriately sized WebP files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.models import News


class Command(BaseCommand):
    help = 'Converts news main photos to compressed WebP copies and updates their records.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report the result without writing files or data.')
        parser.add_argument('--quality', type=int, default=82, help='WebP quality from 0 to 100 (default: 82).')
        parser.add_argument('--max-width', type=int, default=1440, help='Maximum image width in pixels (default: 1440).')

    def handle(self, *args, **options):
        try:
            from PIL import Image, ImageOps
        except ImportError as error:
            raise CommandError('Pillow is required for image optimisation.') from error

        quality = options['quality']
        max_width = options['max_width']
        if not 1 <= quality <= 100:
            raise CommandError('--quality must be between 1 and 100.')
        if max_width < 320:
            raise CommandError('--max-width must be at least 320.')

        media_root = Path(settings.MEDIA_ROOT)
        dry_run = options['dry_run']
        processed = skipped = missing = 0
        source_bytes = output_bytes = 0

        with transaction.atomic():
            for news in News.objects.exclude(main_photo='').order_by('pk'):
                source_name = news.main_photo.name
                source_path = media_root / source_name
                if not source_path.is_file():
                    missing += 1
                    self.stderr.write(f'Missing file for {news.slug}: {source_name}')
                    continue

                target_name = str(Path(source_name).with_suffix('.webp'))
                target_path = media_root / target_name
                if source_name.lower().endswith('.webp') and source_path.stat().st_size:
                    skipped += 1
                    continue

                with Image.open(source_path) as source_image:
                    image = ImageOps.exif_transpose(source_image)
                    if image.width > max_width:
                        height = round(image.height * max_width / image.width)
                        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
                    if image.mode not in {'RGB', 'RGBA'}:
                        image = image.convert('RGBA' if 'transparency' in image.info else 'RGB')

                    encoded = BytesIO()
                    image.save(encoded, format='WEBP', quality=quality, method=6)

                payload = encoded.getvalue()
                source_bytes += source_path.stat().st_size
                output_bytes += len(payload)
                processed += 1

                if not dry_run:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary_path = target_path.with_suffix('.webp.tmp')
                    temporary_path.write_bytes(payload)
                    temporary_path.replace(target_path)
                    news.main_photo.name = target_name
                    news.save(update_fields=('main_photo', 'updated_at'))

            if dry_run:
                transaction.set_rollback(True)

        source_mb = source_bytes / 1024 / 1024
        output_mb = output_bytes / 1024 / 1024
        reduction = (1 - output_bytes / source_bytes) * 100 if source_bytes else 0
        mode = 'previewed' if dry_run else 'optimised'
        self.stdout.write(self.style.SUCCESS(
            f'Images {mode}: {processed} converted, {skipped} already WebP, {missing} missing; '
            f'{source_mb:.2f} MB → {output_mb:.2f} MB ({reduction:.0f}% smaller).'
        ))
