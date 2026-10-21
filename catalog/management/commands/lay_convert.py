import os

from django.core.management.base import BaseCommand, CommandError

from catalog import lay
from catalog.layedit import convert_file


class Command(BaseCommand):
    help = "Перевести файл Sprint Layout между версиями 5 (.lay) и 6 (.lay6); все платы файла, соединения и хвост сохраняются"

    def add_arguments(self, parser):
        parser.add_argument("src", help="Исходный файл .lay или .lay6")
        parser.add_argument("dst", nargs="?", help="Куда записать (по умолчанию — рядом, с расширением новой версии)")
        parser.add_argument("--to", type=int, choices=(5, 6), help="Версия результата (по умолчанию — другая)")

    def handle(self, *args, **opts):
        with open(opts["src"], "rb") as fh:
            data = fh.read()
        try:
            src = lay.parse(data)
        except lay.LayError as exc:
            raise CommandError(f"{opts['src']}: {exc}")
        to = opts["to"] or (5 if src.version == 6 else 6)
        dst = opts["dst"] or os.path.splitext(opts["src"])[0] + (".lay" if to == 5 else ".lay6")
        if os.path.abspath(dst) == os.path.abspath(opts["src"]):
            raise CommandError("Результат совпадает с исходным файлом — укажите другое имя")
        out = convert_file(data, to)
        res = lay.parse(out)
        with open(dst, "wb") as fh:
            fh.write(out)
        objs = sum(len(b.objects) for b in res.boards)
        self.stdout.write(f"{opts['src']} (v{src.version}) → {dst} (v{to}): плат {len(res.boards)}, объектов {objs}")
