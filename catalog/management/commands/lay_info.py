from django.core.management.base import BaseCommand, CommandError

from catalog import lay
from catalog.laytools import ISSUE_TITLES, analyze
from catalog.models import PCBFile


class Command(BaseCommand):
    help = "Сводка и автоматическая проверка плат Sprint Layout: файлы или все платы из базы (--all)"

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="Файлы .lay/.lay6")
        parser.add_argument("--all", action="store_true", help="Проверить все платы LAY в базе")
        parser.add_argument("--clearance", type=float, default=0.3, help="Минимальный зазор, мм")
        parser.add_argument("--min-width", type=float, default=0.25, help="Минимальная ширина дорожки, мм")
        parser.add_argument("--issues", action="store_true", help="Показать места замечаний")

    def handle(self, *args, **opts):
        targets = [(p, p) for p in opts["paths"]]
        if opts["all"]:
            targets += [(f"#{p.pk} {p.title}", p.file.path) for p in PCBFile.objects.exclude(file="") if p.is_lay]
        if not targets:
            raise CommandError("Укажите файлы или --all")
        failed = 0
        for title, path in targets:
            try:
                with open(path, "rb") as fh:
                    data = lay.parse(fh.read())
            except (OSError, lay.LayError) as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"{title}: не читается — {exc}"))
                continue
            a = analyze(data, clearance=opts["clearance"], min_width=opts["min_width"])
            s = a.summary
            drills = ", ".join(f"{n}×⌀{d}" for d, n in s["drills"]) or "нет"
            self.stdout.write(self.style.MIGRATE_HEADING(f"{title}"))
            self.stdout.write(
                f"  Sprint Layout {s['version']}, {s['size_mm'][0]}×{s['size_mm'][1]} мм, медь: {', '.join(s['copper_layers'])}\n"
                f"  площадки: {s['tht_pads']} выводных, {s['smd_pads']} SMD; отверстия: {drills}\n"
                f"  деталей {s['components']}, цепей {s['nets']}, перемычек {s['jumpers']} ({s['jumper_length_mm']} мм)")
            if a.issue_counts:
                counts = ", ".join(f"{ISSUE_TITLES[k].lower()}: {n}" for k, n in a.issue_counts.items())
                self.stdout.write(self.style.WARNING(f"  проверка: {counts}"))
                if opts["issues"]:
                    for i in a.issues:
                        self.stdout.write(f"    ({i.x:.2f}; {-i.y:.2f}) {i.text}")
            else:
                self.stdout.write(self.style.SUCCESS("  проверка: замечаний нет"))
        if failed:
            raise CommandError(f"Не прочитано файлов: {failed}")
