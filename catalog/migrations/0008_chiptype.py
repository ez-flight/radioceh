from django.db import migrations, models
import django.db.models.deletion


CHIP_TYPES = [
    (10, "УНЧ"),
    (20, "Предварительный УНЧ"),
    (30, "FM/AM-радиоприёмник"),
    (40, "УКВ-тракт"),
    (50, "АМ-тракт"),
    (60, "Усилитель ПЧ"),
    (70, "Смеситель"),
    (80, "Операционный усилитель"),
    (90, "УВЧ"),
    (100, "Стереодекодер"),
    (110, "Стабилизатор"),
    (120, "Коммутатор"),
    (130, "Детектор"),
    (140, "Генератор"),
]

NOTE_TO_TYPE = {
    "унч": "УНЧ",
    "укв": "УКВ-тракт",
    "пч ам": "Усилитель ПЧ",
    "пч": "Усилитель ПЧ",
    "смеситель": "Смеситель",
    "ам-тракт": "АМ-тракт",
    "оу": "Операционный усилитель",
    "ам": "АМ-тракт",
    "ам/чм": "FM/AM-радиоприёмник",
}

CHIP_NAME_TO_TYPE = {
    "CXA1191": "FM/AM-радиоприёмник",
}


def seed_types_and_assign(apps, schema_editor):
    ChipType = apps.get_model("catalog", "ChipType")
    Chip = apps.get_model("catalog", "Chip")
    types = {}
    for order, name in CHIP_TYPES:
        types[name] = ChipType.objects.create(name=name, sort_order=order)
    fallback = types["УНЧ"]
    for chip in Chip.objects.all():
        mapped = CHIP_NAME_TO_TYPE.get(chip.name)
        if not mapped:
            mapped = NOTE_TO_TYPE.get((chip.notes or "").strip().lower())
        chip.chip_type = types.get(mapped, fallback)
        chip.save(update_fields=["chip_type"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_chip_pcb_receivers_m2m"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChipType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="Название")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "тип микросхемы",
                "verbose_name_plural": "типы микросхем",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="chip",
            name="chip_type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chips",
                to="catalog.chiptype",
                verbose_name="Тип",
            ),
        ),
        migrations.AlterModelOptions(
            name="chip",
            options={
                "ordering": ["chip_type", "name"],
                "verbose_name": "микросхема",
                "verbose_name_plural": "микросхемы",
            },
        ),
        migrations.RunPython(seed_types_and_assign, noop),
        migrations.AlterField(
            model_name="chip",
            name="chip_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chips",
                to="catalog.chiptype",
                verbose_name="Тип",
            ),
        ),
    ]
