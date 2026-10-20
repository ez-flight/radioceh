import os

from django.core.management.base import BaseCommand, CommandError

from catalog.laymacro import MacroError, describe, parse_macro


class Command(BaseCommand):
    help = "Сводка по макросам Sprint Layout (.lmk) или проверка целой папки (--check)"

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="Файлы .lmk или папки")
        parser.add_argument("--check", action="store_true", help="Только проверить, что все макросы читаются")

    def handle(self, *args, **opts):
        files = []
        for p in opts["paths"]:
            if os.path.isdir(p):
                for dp, _, fs in os.walk(p):
                    files += [os.path.join(dp, f) for f in sorted(fs) if f.lower().endswith(".lmk")]
            else:
                files.append(p)
        if not files:
            raise CommandError("Макросов не найдено")
        ok, bad, skipped = 0, [], 0
        for path in files:
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
                m = parse_macro(data)
            except OSError as exc:
                bad.append((path, str(exc))); continue
            except MacroError as exc:
                if "не поддерживается" in str(exc):
                    skipped += 1
                else:
                    bad.append((path, str(exc)))
                continue
            ok += 1
            if opts["check"]:
                continue
            d = describe(m)
            objs = ", ".join(f"{n} {k}" for k, n in d["objects"].items())
            drills = ", ".join(f"{n}×⌀{dr}" for dr, n in d["drills"]) or "нет"
            self.stdout.write(self.style.MIGRATE_HEADING(path))
            self.stdout.write(f"  версия {d['version']}, {d['size_mm'][0]}×{d['size_mm'][1]} мм; {objs}\n"
                              f"  площадок {d['pads']}, отверстия: {drills}"
                              + (f"\n  описание: {d['description']}" if d["description"] else ""))
        if opts["check"] or len(files) > 1:
            self.stdout.write(f"Прочитано {ok} из {len(files)}" + (f", версий 1–3 пропущено: {skipped}" if skipped else ""))
        for path, why in bad:
            self.stdout.write(self.style.ERROR(f"  {path}: {why}"))
        if bad:
            raise CommandError(f"Не читаются: {len(bad)}")
