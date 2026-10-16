from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_factory_republic_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="original_file",
            field=models.FileField(
                blank=True,
                help_text="PDF, DJVU или JPG/PNG",
                upload_to="articles/",
                validators=[FileExtensionValidator(("pdf", "djvu", "djv", "jpg", "jpeg", "png", "webp"))],
                verbose_name="Оригинал статьи",
            ),
        ),
    ]
