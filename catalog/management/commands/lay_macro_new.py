from django.core.management.base import BaseCommand, CommandError

from catalog.laymacro import MacroError, describe, macro_from_board, parse_macro


class Command(BaseCommand):
    help = "Макрос Sprint Layout (.lmk) из части платы: площадки и маркировка внутри рамки"

    def add_arguments(self, parser):
        parser.add_argument("board", help="Плата .lay/.lay6 (одна плата в файле)")
        parser.add_argument("macro", help="Куда записать .lmk")
        parser.add_argument("--box", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"),
                            help="Рамка в мм, как координаты lay_info (y растёт вниз)")
        parser.add_argument("--origin", nargs=2, type=float, metavar=("X", "Y"),
                            help="Начало координат макроса, мм (по умолчанию — первая площадка в рамке)")
        parser.add_argument("--name", default="", help="Описание макроса (до 100 знаков)")
        parser.add_argument("--copper", action="store_true", help="Взять и дорожки с заливкой из рамки")

    def handle(self, *args, **opts):
        x0, y0, x1, y1 = opts["box"]
        box = (min(x0, x1), -max(y0, y1), max(x0, x1), -min(y0, y1))
        origin = (opts["origin"][0], -opts["origin"][1]) if opts["origin"] else None
        try:
            with open(opts["board"], "rb") as fh:
                data = macro_from_board(fh.read(), box, origin, opts["name"], copper=opts["copper"])
        except (OSError, ValueError, MacroError) as exc:
            raise CommandError(str(exc))
        with open(opts["macro"], "wb") as fh:
            fh.write(data)
        d = describe(parse_macro(data))
        self.stdout.write(self.style.SUCCESS(
            f"Записан {opts['macro']}: версия {d['version']}, площадок {d['pads']}, {d['size_mm'][0]}×{d['size_mm'][1]} мм"))
