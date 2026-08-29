from django.db import migrations


class Migration(migrations.Migration):
    """Join the two valid migration branches created after ``0001``.

    Keep the schema-building branch first so a fresh database receives the
    current uploader field from ``0004`` after the earlier content-field
    alteration from the other ``0002`` branch.
    """

    dependencies = [
        (
            "news",
            "0002_category_newsgallery_alter_news_options_news_excerpt_and_more",
        ),
        ("news", "0006_tag_news_tags"),
    ]

    operations = []
