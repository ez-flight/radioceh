import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


COMMON_CHIPS = [
    ("К174УН7", "СССР", "УНЧ"),
    ("К174УН14", "СССР", "УНЧ"),
    ("К174ХА2", "СССР", "УКВ"),
    ("К174ХА10", "СССР", "УКВ"),
    ("К174УР3", "СССР", "ПЧ АМ"),
    ("К174УР1", "СССР", "ПЧ"),
    ("К174ПС1", "СССР", "смеситель"),
    ("К157ХА2", "СССР", "АМ-тракт"),
    ("К157УД2", "СССР", "ОУ"),
    ("ТА7642", "", "АМ"),
    ("TA2003", "", "АМ/ЧМ"),
    ("CXA1191", "Sony", ""),
    ("TDA2822", "", "УНЧ"),
]


def copy_receiver_links_and_seed(apps, schema_editor):
    PCBFile = apps.get_model("catalog", "PCBFile")
    Chip = apps.get_model("catalog", "Chip")
    Group = apps.get_model("auth", "Group")
    through = PCBFile.receivers.through
    rows = [
        through(pcbfile_id=pcb.pk, receiver_id=pcb.receiver_id)
        for pcb in PCBFile.objects.exclude(receiver_id=None)
    ]
    if rows:
        through.objects.bulk_create(rows, ignore_conflicts=True)
    Chip.objects.bulk_create(
        [Chip(name=name, manufacturer=maker, notes=notes) for name, maker, notes in COMMON_CHIPS],
        ignore_conflicts=True,
    )
    Group.objects.get_or_create(name="продавец")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("catalog", "0006_receiver_is_hidden"),
    ]

    operations = [
        migrations.CreateModel(
            name="Chip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="Маркировка")),
                ("manufacturer", models.CharField(blank=True, max_length=120, verbose_name="Производитель")),
                ("notes", models.CharField(blank=True, max_length=220, verbose_name="Примечание")),
            ],
            options={
                "verbose_name": "микросхема",
                "verbose_name_plural": "микросхемы",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pcb_files",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Кто добавил",
            ),
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="developed_at",
            field=models.DateField(default=django.utils.timezone.localdate, verbose_name="Дата разработки"),
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="chips",
            field=models.ManyToManyField(
                blank=True,
                related_name="pcb_files",
                to="catalog.chip",
                verbose_name="Микросхемы",
            ),
        ),
        migrations.AddField(
            model_name="pcbfile",
            name="receivers",
            field=models.ManyToManyField(
                related_name="pcb_projects_tmp",
                to="catalog.receiver",
                verbose_name="Приёмники",
            ),
        ),
        migrations.AlterField(
            model_name="pcbfile",
            name="file",
            field=models.FileField(
                help_text="LAY, PCB, ZIP или PDF",
                upload_to="pcb/",
                validators=[django.core.validators.FileExtensionValidator(("lay", "pcb", "zip", "pdf"))],
                verbose_name="Файл платы",
            ),
        ),
        migrations.AlterField(
            model_name="pcbfile",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Комментарий"),
        ),
        migrations.AlterModelOptions(
            name="pcbfile",
            options={
                "ordering": ["-developed_at", "title"],
                "verbose_name": "печатная плата",
                "verbose_name_plural": "печатные платы",
            },
        ),
        migrations.RunPython(copy_receiver_links_and_seed, noop),
        migrations.RemoveField(
            model_name="pcbfile",
            name="receiver",
        ),
        migrations.AlterField(
            model_name="pcbfile",
            name="receivers",
            field=models.ManyToManyField(
                related_name="pcb_files",
                to="catalog.receiver",
                verbose_name="Приёмники",
            ),
        ),
    ]
