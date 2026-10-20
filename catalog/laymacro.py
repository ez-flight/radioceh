"""Макросы Sprint Layout (.lmk): чтение версий 4–6, запись версий 5–6, сборка макроса из части платы.

Устройство файла — docs/sprint-layout-format.md, раздел «Макросы (.LMK)»:
версия + 33 AA FF, u32 число объектов, объекты как в .lay той же версии (у v4 — свои, целочисленные),
по u32 на каждую площадку (пустые списки связей), описание — строка Паскаля на 100 знаков, один байт.
"""
import struct
from dataclasses import dataclass, field

from catalog import lay

MAGIC = b"\x33\xaa\xff"
TAIL_TEXT = 100


class MacroError(ValueError):
    pass


@dataclass
class Macro:
    version: int
    objects: list                     # lay.LayObject
    description: str = ""
    flag: int = 0                     # последний байт файла, смысл не расшифрован
    errors: list = field(default_factory=list)

    @property
    def unit(self):
        return 100.0 if self.version < 6 else 10000.0

    @property
    def pads(self):
        return [o for o in self.objects if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD)]

    def layfile(self):
        """Макрос как плата — для отрисовки (lay.render_svg) и проверок laytools."""
        version = 5 if self.version < 6 else 6
        return lay.LayFile(version, [lay.LayBoard("макрос", 0, 0, [0] * 7, self.objects)])


# ------------------------------------------------------------------ версия 4: целые числа, свои хвосты объектов
def _read_v4(r, child=False):
    start = r.pos
    kind = r.u8()
    x, y, out, inner, width = struct.unpack("<5i", r.take(20))
    r.take(1)
    layer, shape = r.u8(), r.u8()
    r.take(7)
    (start_angle,) = struct.unpack("<i", r.take(4))
    r.take(75 - (r.pos - start))
    if kind not in lay.OBJECT_TYPES and kind != 1:
        raise MacroError(f"Неизвестный тип объекта {kind} по смещению {start:#x}")
    o = lay.LayObject(type=kind, x=float(x), y=float(y), out=float(out), inner=float(inner), line_width=width,
                      layer=layer, shape=shape, start_angle=start_angle, flag=0, ground_distance=0,
                      cutoff=False, plated=False)
    if not child:
        o.text = r.take(r.count(1, len(r.data))).decode("cp1251", "replace")
        n = r.count(4, 100000)
        o.groups = struct.unpack(f"<{n}I", r.take(4 * n))
    if kind == lay.OBJ_TEXT:
        n = r.count(75, 100000)
        o.children = [_read_v4(r, True) for _ in range(n)]
        return o
    if kind in (1, lay.OBJ_CIRCLE, lay.OBJ_SMD_PAD):          # тип 1 не расшифрован, SMD — центр и половины сторон
        if kind == lay.OBJ_SMD_PAD:
            hx, hy = abs(out), abs(inner)
            o.points = [(x - hx, y + hy), (x - hx, y - hy), (x + hx, y - hy), (x + hx, y + hy)]
        return o
    if kind == lay.OBJ_THT_PAD:
        r.take(4)                                            # одно поле i32: -1 или номер (не расшифровано)
        return o
    (n,) = struct.unpack("<i", r.take(4))
    o.points = [tuple(float(v) for v in struct.unpack("<ii", r.take(8))) for _ in range(max(n, 0))]
    return o


def parse_macro(data):
    if len(data) < 8 or data[1:4] != MAGIC:
        raise MacroError("Это не макрос Sprint Layout")
    version = data[0]
    if version not in (4, 5, 6):
        raise MacroError(f"Версия макроса {version} не поддерживается (умеем 4–6)")
    r = lay._Reader(data)
    r.take(4)
    try:
        n = r.count(20, 100000)
        objs = [(_read_v4(r) if version == 4 else lay._read_object(r, version)) for _ in range(n)]
        for i, o in enumerate(objs):
            o.index = i
        for o in objs:
            if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD):
                r.take(4 * r.count(4, 100000))
    except (lay.LayError, struct.error, IndexError) as exc:
        raise MacroError(f"Макрос не читается: {exc}") from exc
    description, flag = "", 0
    if len(r.data) - r.pos >= TAIL_TEXT + 2:
        description = r.short_string(TAIL_TEXT).strip()
        flag = r.u8()
    return Macro(version, objs, description, flag)


# ------------------------------------------------------------------ запись
def build_macro(objects, version=5, description=""):
    """objects — объекты layedit.Obj (верхнего уровня) в единицах файла нужной версии (5 или 6).
    Описание — до 100 знаков cp1251, показывается Sprint в окне макросов."""
    if version not in (5, 6):
        raise MacroError("Писать умеем макросы версий 5 и 6")
    text = description.encode("cp1251", "replace")[:TAIL_TEXT]
    pads = sum(1 for o in objects if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD))
    return (bytes([version]) + MAGIC + struct.pack("<I", len(objects)) + b"".join(o.to_bytes() for o in objects)
            + b"\0\0\0\0" * pads + bytes([len(text)]) + text + b"\0" * (TAIL_TEXT - len(text)) + b"\0")


def macro_from_board(data, box_mm, origin_mm=None, description="", copper=False):
    """Макрос из части платы: площадки и рисунок маркировки, целиком лежащие в box_mm=(x0, y0, x1, y1)
    в мм файла (ось Y вверх); дорожки и заливка (медь) — только при copper=True, контур (слой 7) — никогда. Начало координат — origin_mm или центр первой площадки. Возвращает байты макроса
    той же версии, что и плата."""
    from catalog.layedit import LayDoc

    doc = LayDoc(data)
    u = doc.unit
    x0, y0, x1, y1 = (v * u for v in box_mm)

    def inside(o):
        if o.type in (5, 2):
            xs, ys = [o.xy[0]], [o.xy[1]]
            r = abs(o.get("<f", 9))
            xs, ys = [xs[0] - r, xs[0] + r], [ys[0] - r, ys[0] + r]
        elif o.type == 7:
            pts = [p for c in o.children for p in (c.points or [])]
            xs, ys = [p[0] for p in pts] or [o.xy[0]], [p[1] for p in pts] or [o.xy[1]]
        else:
            xs, ys = [p[0] for p in o.points], [p[1] for p in o.points]
        return xs and min(xs) >= x0 and max(xs) <= x1 and min(ys) >= y0 and max(ys) <= y1

    is_copper = lambda o: o.type in (4, 5, 6) and o.layer in (1, 3, 5, 6)
    picked = [o for o in doc.objects if o.layer != 7 and (copper or not is_copper(o)) and inside(o)]
    if not any(o.type in (2, 8) for o in picked):
        raise MacroError("В рамке нет площадок")
    if origin_mm is None:
        first = next(o for o in picked if o.type in (2, 8))
        ox, oy = first.xy if first.type == 2 else (sum(p[0] for p in first.points) / 4, sum(p[1] for p in first.points) / 4)
    else:
        ox, oy = origin_mm[0] * u, origin_mm[1] * u
    for o in picked:
        o.move(-ox, -oy)
        o.groups = []
    return build_macro(picked, doc.version, description)


def describe(m):
    """Сводка макроса: версия, объекты по типам, площадки, габарит в мм."""
    from collections import Counter
    names = {1: "тип 1", 2: "выводных", 4: "многоугольников", 5: "окружностей", 6: "линий", 7: "текстов", 8: "SMD"}
    k = 1.0 / m.unit
    xs, ys = [], []
    for o in m.objects:
        pts = list(o.points or []) + [p for c in (o.children or []) for p in (c.points or [])]
        if o.type in (lay.OBJ_THT_PAD, lay.OBJ_CIRCLE):
            r = abs(o.out)
            pts += [(o.x - r, o.y - r), (o.x + r, o.y + r)]
        xs += [p[0] * k for p in pts]; ys += [p[1] * k for p in pts]
    size = (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)) if xs else (0, 0)
    counts = Counter(o.type for o in m.objects)
    drills = Counter(round(2 * abs(o.inner) * k, 2) for o in m.objects if o.type == lay.OBJ_THT_PAD)
    return {"version": m.version, "objects": {names.get(t, str(t)): n for t, n in sorted(counts.items())},
            "pads": len(m.pads), "size_mm": size, "drills": sorted(drills.items()), "description": m.description}
