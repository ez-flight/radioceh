from django.db import migrations


def add_fm_band(apps, schema_editor):
    Band = apps.get_model("catalog", "Band")
    Band.objects.get_or_create(code="FM", defaults={"name": "FM (87,5–108 МГц)"})


def remove_fm_band(apps, schema_editor):
    Band = apps.get_model("catalog", "Band")
    Band.objects.filter(code="FM").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0011_receiver_produced_count_drop_years_text"),
    ]

    operations = [
        migrations.RunPython(add_fm_band, remove_fm_band),
    ]
