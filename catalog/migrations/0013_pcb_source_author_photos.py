from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_band_fm"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pcbfile",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="Если плата скачана со стороннего ресурса.",
                verbose_name="Ссылка на статью",
            ),
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="author_name",
            field=models.CharField(
                blank=True,
                help_text="Ник с исходной статьи. Если автор зарегистрирован на сайте — укажите его логин.",
                max_length=80,
                verbose_name="Ник автора",
            ),
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="authored_pcbs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Автор на сайте",
            ),
        ),
        migrations.CreateModel(
            name="PCBPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="pcb/photos/", verbose_name="Фото")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                (
                    "pcb",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="catalog.pcbfile",
                        verbose_name="Плата",
                    ),
                ),
            ],
            options={
                "verbose_name": "фото проекта",
                "verbose_name_plural": "фото проекта",
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
