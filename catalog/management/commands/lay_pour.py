from django.core.management.base import BaseCommand, CommandError
from shapely.geometry import box

from catalog import lay
from catalog.laypour import pour
from catalog.laytools import plural


class Command(BaseCommand):
    help = ("Заливка свободного места медью цепи, на которой стоит точка --at (обычно земля). "
            "Координаты в мм как в lay_info/lay_diff (y вниз)")

    def add_arguments(self, parser):
        parser.add_argument("board")
        parser.add_argument("out")
        parser.add_argument("--at", nargs=2, type=float, required=True, metavar=("X", "Y"),
                            help="Точка на меди цепи, которой заливать")
        parser.add_argument("--layer", type=int, default=3, help="Слой меди: 1 — верх, 3 — низ (по умолчанию)")
        parser.add_argument("--clearance", type=float, default=0.4, help="Зазор до чужой меди, мм")
        parser.add_argument("--edge", type=float, default=0.6, help="Отступ от края платы и вырезов, мм")
        parser.add_argument("--min-neck", type=float, default=0.5, help="Убирать перешейки уже, мм")
        parser.add_argument("--region", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                            help="Заливать только внутри прямоугольника")

    def handle(self, *args, **opts):
        try:
            with open(opts["board"], "rb") as fh:
                data = fh.read()
            region = None
            if opts["region"]:
                x0, y0, x1, y1 = opts["region"]
                region = box(min(x0, x1), -max(y0, y1), max(x0, x1), -min(y0, y1))
            x, y = opts["at"]
            new, r = pour(data, (x, -y), layer=opts["layer"], clearance=opts["clearance"], edge=opts["edge"],
                          min_neck=opts["min_neck"], region=region)
        except (OSError, lay.LayError, ValueError, NotImplementedError) as exc:
            raise CommandError(str(exc))
        with open(opts["out"], "wb") as fh:
            fh.write(new)
        self.stdout.write(f"Залито {r.area} мм²: {r.pieces} {plural(r.pieces, 'кусок', 'куска', 'кусков')}, "
                          f"{r.polygons} {plural(r.polygons, 'многоугольник', 'многоугольника', 'многоугольников')}")
        if r.skipped:
            self.stdout.write(self.style.WARNING(
                f"Не залито {r.skipped} {plural(r.skipped, 'кусок', 'куска', 'кусков')} ({r.skipped_area} мм²): "
                "не касаются цепи — нужны перемычки или дорожки"))
