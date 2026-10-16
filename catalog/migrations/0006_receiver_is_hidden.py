from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_category_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiver",
            name="is_hidden",
            field=models.BooleanField(default=False, verbose_name="Скрыть"),
        ),
    ]
