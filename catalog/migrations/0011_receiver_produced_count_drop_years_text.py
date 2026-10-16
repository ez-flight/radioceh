from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_article_original_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="receiver",
            name="produced_count",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Выпущено, шт."),
        ),
        migrations.RemoveField(
            model_name="receiver",
            name="years_text",
        ),
        migrations.AlterField(
            model_name="receiver",
            name="year_start",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Начало выпуска"),
        ),
        migrations.AlterField(
            model_name="receiver",
            name="year_end",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Конец выпуска"),
        ),
    ]
