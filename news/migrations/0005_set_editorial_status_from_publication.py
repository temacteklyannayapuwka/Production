from django.db import migrations
from django.utils import timezone


def set_editorial_status(apps, schema_editor):
    News = apps.get_model('news', 'News')
    now = timezone.now()

    News.objects.filter(is_published=False).update(editorial_status='draft')
    News.objects.filter(is_published=True, date_start__gt=now).update(editorial_status='scheduled')
    News.objects.filter(is_published=True, date_start__lte=now).update(editorial_status='published')


def reverse_editorial_status(apps, schema_editor):
    News = apps.get_model('news', 'News')
    News.objects.filter(editorial_status='draft').update(is_published=False)
    News.objects.exclude(editorial_status='draft').update(is_published=True)


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0004_advertisement_news_editorial_status_and_more'),
    ]

    operations = [
        migrations.RunPython(set_editorial_status, reverse_editorial_status),
    ]
