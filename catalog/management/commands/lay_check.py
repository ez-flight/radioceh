import csv
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from catalog import lay
from catalog.laytools import check_netlist, export_netlist, plural

HELP_FORMAT = """Список соединений — CSV (цепь;x;y;метка, разделитель «;» или «,») или JSON {"цепь": [[x, y, "метка"], …]}.
Координаты в мм как их печатают lay_info и lay_diff: y растёт вниз (в файле Sprint — вверх)."""


def read_netlist(path):
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    nets = {}
    if path.lower().endswith(".json"):
        for name, points in json.loads(text).items():
            nets[name] = [(float(p[0]), -float(p[1]), str(p[2]) if len(p) > 2 else f"{name}:{i + 1}")
                          for i, p in enumerate(points)]
        return nets
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,\t")
    for row in csv.reader(text.splitlines(), dialect):
        if not row or row[0].startswith("#") or row[0].strip().lower() in ("net", "цепь"):
            continue
        name, x, y = row[0].strip(), float(row[1].replace(",", ".")), float(row[2].replace(",", "."))
        label = row[3].strip() if len(row) > 3 and row[3].strip() else f"{name}:{len(nets.get(name, [])) + 1}"
        nets.setdefault(name, []).append((x, -y, label))
    return nets


class Command(BaseCommand):
    help = "Сверка платы Sprint Layout со списком соединений или выгрузка списка из платы (--export)"

    def add_arguments(self, parser):
        parser.add_argument("board")
        parser.add_argument("netlist", nargs="?", help=HELP_FORMAT)
        parser.add_argument("--export", metavar="CSV", help="Записать список соединений платы (- — в консоль)")

    def handle(self, *args, **opts):
        try:
            with open(opts["board"], "rb") as fh:
                lay_file = lay.parse(fh.read())
        except (OSError, lay.LayError) as exc:
            raise CommandError(str(exc))
        if opts["export"]:
            rows = export_netlist(lay_file)
            out = sys.stdout if opts["export"] == "-" else open(opts["export"], "w", encoding="utf-8", newline="")
            w = csv.writer(out, delimiter=";")
            w.writerow(["net", "x", "y", "label"])
            for name, x, y, label in rows:
                w.writerow([name, x, round(-y, 3), label])
            if out is not sys.stdout:
                out.close()
                self.stdout.write(f"Записано площадок: {len(rows)}, цепей: {len({r[0] for r in rows})}")
            return
        if not opts["netlist"]:
            raise CommandError("Укажите список соединений или --export")
        try:
            netlist = read_netlist(opts["netlist"])
        except (OSError, ValueError, IndexError, json.JSONDecodeError) as exc:
            raise CommandError(f"Список соединений не читается: {exc}")
        r = check_netlist(lay_file, netlist)
        self.stdout.write(f"Цепей в списке: {r.nets}, собраны верно: {r.ok}")
        for name, pieces in r.broken:
            self.stdout.write(self.style.ERROR(f"  {name}: разорвана на {len(pieces)} {plural(len(pieces), 'кусок', 'куска', 'кусков')} — "
                                               + " | ".join(", ".join(p) for p in pieces)))
        for a, b, label in r.shorts:
            self.stdout.write(self.style.ERROR(f"  замыкание: {a} и {b} (у {label})"))
        for name, label, x, y, why in r.missing:
            self.stdout.write(self.style.WARNING(f"  {name} {label} ({x:.2f}; {-y:.2f}): {why}"))
        if r.passed:
            self.stdout.write(self.style.SUCCESS("Плата соответствует списку соединений"))
        else:
            raise CommandError("Плата не соответствует списку соединений")
