"""Image handling shared by the news models and maintenance commands."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile


WEBP_QUALITY = 82
MAX_IMAGE_WIDTH = 1440


def convert_pending_upload_to_webp(image_field):
    """Return a compressed WebP upload or ``None`` when conversion is unnecessary.

    Only newly uploaded non-WebP files are transformed. Existing files keep
    their current name, so ordinary edits in the admin do not recompress them.
    """
    if not image_field or image_field._committed:
        return None

    source_name = Path(image_field.name or 'image').name
    if source_name.lower().endswith('.webp'):
        return None

    try:
        from PIL import Image, ImageOps

        source_file = image_field.file
        source_file.seek(0)
        with Image.open(source_file) as source_image:
            image = ImageOps.exif_transpose(source_image)
            if image.width > MAX_IMAGE_WIDTH:
                height = round(image.height * MAX_IMAGE_WIDTH / image.width)
                image = image.resize((MAX_IMAGE_WIDTH, height), Image.Resampling.LANCZOS)
            if image.mode not in {'RGB', 'RGBA'}:
                image = image.convert('RGBA' if 'transparency' in image.info else 'RGB')

            buffer = BytesIO()
            image.save(buffer, format='WEBP', quality=WEBP_QUALITY, method=6)
    except (OSError, ValueError):
        return None

    target_name = f'{Path(source_name).stem or "image"}.webp'
    return target_name, ContentFile(buffer.getvalue(), name=target_name)
