from django.core.management.base import BaseCommand, CommandError

from catalog import lay
from catalog.laytools import diff


class Command(BaseCommand):
    help = "Сравнение двух версий платы Sprint Layout по соединениям площадок, которые есть в обеих"

    def add_arguments(self, parser):
        parser.add_argument("old")
        parser.add_argument("new")

    def handle(self, *args, **opts):
        try:
            a = lay.parse(open(opts["old"], "rb").read())
            b = lay.parse(open(opts["new"], "rb").read())
        except (OSError, lay.LayError) as exc:
            raise CommandError(str(exc))
        d = diff(a, b)
        self.stdout.write(f"Общих площадок: {d.matched}; только в старой: {d.only_a}; только в новой: {d.only_b}")
        for title, items in (("Разорвано", d.splits), ("Слито", d.merges)):
            if items:
                self.stdout.write(self.style.WARNING(f"{title}: {len(items)}"))
                for x, y, text in items[:30]:
                    self.stdout.write(f"  ({x:.2f}; {-y:.2f}) {text}")
        if not d.splits and not d.merges:
            self.stdout.write(self.style.SUCCESS("Соединения общих площадок не изменились"))
