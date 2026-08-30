from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0007_merge_news_migration_branches"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="legacy_k2_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name="ID в старом K2",
            ),
        ),
        migrations.AddField(
            model_name="tag",
            name="legacy_k2_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name="ID в старом K2",
            ),
        ),
        migrations.AddField(
            model_name="news",
            name="legacy_k2_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name="ID в старом K2",
            ),
        ),
    ]

