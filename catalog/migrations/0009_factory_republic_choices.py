from django.db import migrations, models


SSRS = (
    "Азербайджанская ССР",
    "Армянская ССР",
    "Белорусская ССР",
    "Грузинская ССР",
    "Казахская ССР",
    "Киргизская ССР",
    "Латвийская ССР",
    "Литовская ССР",
    "Молдавская ССР",
    "РСФСР",
    "Таджикская ССР",
    "Туркменская ССР",
    "Узбекская ССР",
    "Украинская ССР",
    "Эстонская ССР",
)


def split_places(apps, schema_editor):
    Factory = apps.get_model("catalog", "Factory")
    for factory in Factory.objects.all():
        raw = (factory.republic or "").strip()
        republic = ""
        region = ""
        for ssr in sorted(SSRS, key=len, reverse=True):
            if ssr in raw:
                republic = ssr
                region = raw.replace(ssr, "").strip(" ,")
                break
        if not republic and raw:
            region = raw
        factory.republic = republic
        factory.region = region
        factory.save(update_fields=["republic", "region"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_chiptype"),
    ]

    operations = [
        migrations.AddField(
            model_name="factory",
            name="region",
            field=models.CharField(blank=True, max_length=180, verbose_name="Область / край"),
        ),
        migrations.RunPython(split_places, noop),
        migrations.AlterField(
            model_name="factory",
            name="republic",
            field=models.CharField(
                blank=True,
                choices=[
                    ("РСФСР", "РСФСР"),
                    ("Украинская ССР", "Украинская ССР"),
                    ("Белорусская ССР", "Белорусская ССР"),
                    ("Узбекская ССР", "Узбекская ССР"),
                    ("Казахская ССР", "Казахская ССР"),
                    ("Грузинская ССР", "Грузинская ССР"),
                    ("Азербайджанская ССР", "Азербайджанская ССР"),
                    ("Литовская ССР", "Литовская ССР"),
                    ("Молдавская ССР", "Молдавская ССР"),
                    ("Латвийская ССР", "Латвийская ССР"),
                    ("Киргизская ССР", "Киргизская ССР"),
                    ("Таджикская ССР", "Таджикская ССР"),
                    ("Армянская ССР", "Армянская ССР"),
                    ("Туркменская ССР", "Туркменская ССР"),
                    ("Эстонская ССР", "Эстонская ССР"),
                ],
                max_length=40,
                verbose_name="Республика СССР",
            ),
        ),
        migrations.AlterField(
            model_name="factory",
            name="country_now",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Россия", "Россия"),
                    ("Украина", "Украина"),
                    ("Беларусь", "Беларусь"),
                    ("Узбекистан", "Узбекистан"),
                    ("Казахстан", "Казахстан"),
                    ("Грузия", "Грузия"),
                    ("Азербайджан", "Азербайджан"),
                    ("Литва", "Литва"),
                    ("Молдова", "Молдова"),
                    ("Латвия", "Латвия"),
                    ("Кыргызстан", "Кыргызстан"),
                    ("Таджикистан", "Таджикистан"),
                    ("Армения", "Армения"),
                    ("Туркменистан", "Туркменистан"),
                    ("Эстония", "Эстония"),
                ],
                max_length=40,
                verbose_name="Страна сейчас",
            ),
        ),
    ]
