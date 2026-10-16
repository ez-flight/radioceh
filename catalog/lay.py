"""Чтение файлов Sprint Layout 5/6 (.lay, .lay6) и отрисовка в SVG.

Формат закрытый. Структуры взяты из реверс-инжиниринга
https://github.com/sergey-raevskiy/xlay (lay6) и сверены на файлах 5-й версии:
заголовок и объекты совпадают, отличаются единицы (1/100 мм против 1/10000 мм),
углы дуг (градусы против тысячных долей) и у текстов v5 нет блока компонента.
"""

import math
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from html import escape

MAGIC = b"\x33\xaa\xff"

OBJ_THT_PAD = 2
OBJ_POLY = 4
OBJ_CIRCLE = 5
OBJ_LINE = 6
OBJ_TEXT = 7
OBJ_SMD_PAD = 8
OBJECT_TYPES = {OBJ_THT_PAD, OBJ_POLY, OBJ_CIRCLE, OBJ_LINE, OBJ_TEXT, OBJ_SMD_PAD}

# Слои Sprint Layout: код -> (id, подпись, цвет как в самой программе)
LAYERS = {
    1: ("C1", "Медь, верх (К1)", "#1e6af9"),
    2: ("S1", "Маркировка, верх (М1)", "#ff2a2a"),
    3: ("C2", "Медь, низ (К2)", "#00ba00"),
    4: ("S2", "Маркировка, низ (М2)", "#e1d704"),
    5: ("I1", "Внутренний слой 1", "#c27c14"),
    6: ("I2", "Внутренний слой 2", "#eeb662"),
    7: ("O", "Контур платы (Ф)", "#ffffff"),
}
GROUND_COLORS = {1: "#0c3f9e", 3: "#006b00"}
METAL_COLOR = "#51e3fd"
BACKGROUND = "#000000"
# Порядок отрисовки «вид сверху»: нижние слои первыми
DRAW_ORDER = [3, 4, 5, 6, 1, 2, 7]

MAX_OBJECTS = 200_000
MAX_POINTS = 1_000_000


class LayError(ValueError):
    pass


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise LayError("Файл обрывается раньше времени")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def u8(self):
        return self.take(1)[0]

    def u32(self):
        return self.unpack("<I")[0]

    def count(self, item_size, limit):
        n = self.u32()
        if n > limit or n * item_size > len(self.data) - self.pos:
            raise LayError("Повреждённый счётчик элементов")
        return n

    def short_string(self, size):
        length = self.u8()
        return self.take(size)[:min(length, size)].decode("cp1251", "replace")

    def long_string(self):
        return self.take(self.count(1, len(self.data))).decode("cp1251", "replace")


@dataclass
class LayObject:
    type: int
    x: float
    y: float
    out: float
    inner: float
    line_width: int
    layer: int
    shape: int
    start_angle: int
    flag: int
    ground_distance: int
    cutoff: bool
    plated: bool
    text: str = ""
    points: list = field(default_factory=list)
    children: list = field(default_factory=list)


@dataclass
class LayBoard:
    name: str
    size_x: float
    size_y: float
    ground_planes: list
    objects: list


@dataclass
class LayFile:
    version: int
    boards: list

    @property
    def unit(self):
        """Сколько единиц файла в одном миллиметре."""
        return 100.0 if self.version < 6 else 10000.0

    @property
    def angle_unit(self):
        return 1.0 if self.version < 6 else 1000.0


def _read_object(r, version, child=False, depth=0):
    start = r.pos
    (kind, x, y, out, inner, line_width, _, layer, shape) = r.unpack("<B4fIBBB")
    if kind not in OBJECT_TYPES:
        raise LayError(f"Неизвестный тип объекта {kind} по смещению {start:#x}")
    r.take(4)  # не разобрано
    r.take(3)  # id компонента, выделение
    (start_angle,) = r.unpack("<I")
    r.take(5)
    flag = r.u8()
    (ground_distance,) = r.unpack("<I")
    r.take(6)
    flip_cutoff = r.take(2)
    r.take(4)  # поворот
    plated = r.u8()
    r.take(19)
    assert r.pos - start == 77

    obj = LayObject(
        type=kind, x=x, y=y, out=out, inner=inner, line_width=line_width,
        layer=layer, shape=shape, start_angle=start_angle, flag=flag,
        ground_distance=ground_distance, cutoff=bool(flip_cutoff[1]), plated=bool(plated),
    )
    if not child:
        obj.text = r.long_string()
        r.long_string()  # маркер
        r.take(4 * r.count(4, MAX_OBJECTS))  # группы

    if kind == OBJ_CIRCLE:
        return obj
    if kind == OBJ_TEXT:
        if depth > 2:
            raise LayError("Слишком глубокая вложенность текста")
        n = r.count(77, MAX_OBJECTS)
        obj.children = [_read_object(r, version, True, depth + 1) for _ in range(n)]
        if shape == 1 and version >= 6 and not child:
            r.unpack("<ffBd")
            r.long_string()  # корпус
            r.long_string()  # комментарий
            r.u8()
        return obj

    n = r.count(8, MAX_POINTS)
    raw = r.take(8 * n)
    obj.points = list(struct.iter_unpack("<ff", raw))
    return obj


def parse(data):
    if len(data) < 8 or data[1:4] != MAGIC:
        raise LayError("Это не файл Sprint Layout")
    version = data[0]
    if version not in (5, 6):
        raise LayError(f"Версия формата {version} не поддерживается")
    r = _Reader(data)
    r.take(4)
    boards = []
    for _ in range(r.count(534, 100)):
        name = r.short_string(30)
        r.take(4)
        size_x, size_y = r.unpack("<II")
        ground_planes = list(r.take(7))
        r.take(16 + 8 + 1 + 3 + 7 + 2)  # сетка, масштаб, вид, активный и видимые слои
        r.short_string(200)
        r.short_string(200)
        r.take(24 + 8 + 8 + 1)  # подложки, центр, многослойность
        n = r.count(77, MAX_OBJECTS)
        objects = [_read_object(r, version) for _ in range(n)]
        for obj in objects:
            if obj.type in (OBJ_THT_PAD, OBJ_SMD_PAD):
                r.take(4 * r.count(4, MAX_OBJECTS))  # соединения
        boards.append(LayBoard(name.strip(), size_x, size_y, ground_planes, objects))
    if not boards:
        raise LayError("В файле нет плат")
    return LayFile(version, boards)


class _SvgBuilder:
    def __init__(self, lay):
        self.k = 1.0 / lay.unit
        self.angle_k = 1.0 / lay.angle_unit
        self.version = lay.version
        self.min_x = self.min_y = math.inf
        self.max_x = self.max_y = -math.inf

    def _extend(self, sx, sy):
        self.min_x, self.max_x = min(self.min_x, sx), max(self.max_x, sx)
        self.min_y, self.max_y = min(self.min_y, sy), max(self.max_y, sy)

    def pt(self, x, y):
        sx, sy = x * self.k, -y * self.k
        self._extend(sx, sy)
        return sx, sy

    @staticmethod
    def num(v):
        return f"{v:.3f}".rstrip("0").rstrip(".") or "0"

    def path(self, points, close=False):
        parts = []
        for i, (x, y) in enumerate(points):
            sx, sy = self.pt(x, y)
            parts.append(f"{'M' if i == 0 else 'L'}{self.num(sx)} {self.num(sy)}")
        if close:
            parts.append("Z")
        return "".join(parts)

    def line(self, obj, color, grow=0.0):
        if len(obj.points) < 2:
            return ""
        width = max(obj.line_width * self.k, 0.05) + grow
        return (f'<path d="{self.path(obj.points)}" fill="none" stroke="{color}" '
                f'stroke-width="{self.num(width)}" stroke-linecap="round" stroke-linejoin="round"/>')

    def poly(self, obj, color, grow=0.0):
        if len(obj.points) < 3:
            return ""
        if obj.type == OBJ_SMD_PAD:
            width = grow
        else:
            width = max(obj.line_width * self.k, 0.0) + grow
        stroke = f' stroke="{color}" stroke-width="{self.num(width)}" stroke-linejoin="round"' if width else ""
        return f'<path d="{self.path(obj.points, close=True)}" fill="{color}"{stroke}/>'

    def circle(self, obj, color, grow=0.0):
        r_out, r_in = abs(obj.out) * self.k, abs(obj.inner) * self.k
        radius = (r_out + r_in) / 2
        width = abs(r_out - r_in) + grow
        if radius <= 0:
            return ""
        start = (obj.start_angle * self.angle_k) % 360
        end = (obj.line_width * self.angle_k) % 360
        cx, cy = self.pt(obj.x, obj.y)
        full = math.isclose(start, end)
        span = 360 if full else (end - start) % 360
        # В границы попадают только точки, через которые реально проходит дуга
        for step in range(0, 361, 15):
            if step <= span:
                a = math.radians(start + step)
                self._extend(cx + radius * math.cos(a), cy - radius * math.sin(a))
        common = f'fill="none" stroke="{color}" stroke-width="{self.num(width)}" stroke-linecap="round"'
        if full:
            return f'<circle cx="{self.num(cx)}" cy="{self.num(cy)}" r="{self.num(radius)}" {common}/>'
        a0, a1 = math.radians(start), math.radians(end)
        x0, y0 = cx + radius * math.cos(a0), cy - radius * math.sin(a0)
        x1, y1 = cx + radius * math.cos(a1), cy - radius * math.sin(a1)
        large = 1 if span > 180 else 0
        return (f'<path d="M{self.num(x0)} {self.num(y0)}A{self.num(radius)} {self.num(radius)} 0 {large} 0 '
                f'{self.num(x1)} {self.num(y1)}" {common}/>')

    def pad(self, obj, color, grow=0.0):
        r = abs(obj.out) * self.k + grow
        cx, cy = self.pt(obj.x, obj.y)
        shape = obj.shape if 1 <= obj.shape <= 9 else 1
        base = (shape - 1) % 3  # 0 круг, 1 восьмиугольник, 2 квадрат
        stretch = (shape - 1) // 3  # 0 обычная, 1 по горизонтали, 2 по вертикали
        hx = r * (2 if stretch == 1 else 1)
        hy = r * (2 if stretch == 2 else 1)
        self._extend(cx - hx, cy - hy)
        self._extend(cx + hx, cy + hy)
        n = self.num
        if base == 2:
            return f'<rect x="{n(cx - hx)}" y="{n(cy - hy)}" width="{n(2 * hx)}" height="{n(2 * hy)}" fill="{color}"/>'
        if base == 1:
            c = r * (1 - math.tan(math.pi / 8))
            pts = [(-hx + c, -hy), (hx - c, -hy), (hx, -hy + c), (hx, hy - c),
                   (hx - c, hy), (-hx + c, hy), (-hx, hy - c), (-hx, -hy + c)]
            d = "".join(f"{'M' if i == 0 else 'L'}{n(cx + px)} {n(cy + py)}" for i, (px, py) in enumerate(pts))
            return f'<path d="{d}Z" fill="{color}"/>'
        if stretch == 0:
            return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{color}"/>'
        return (f'<rect x="{n(cx - hx)}" y="{n(cy - hy)}" width="{n(2 * hx)}" height="{n(2 * hy)}" '
                f'rx="{n(r)}" fill="{color}"/>')

    def drill(self, obj):
        r = abs(obj.inner) * self.k
        if r <= 0:
            return ""
        cx, cy = self.pt(obj.x, obj.y)
        return f'<circle cx="{self.num(cx)}" cy="{self.num(cy)}" r="{self.num(r)}"/>'

    def draw(self, obj, color, grow=0.0):
        if obj.type == OBJ_LINE:
            return self.line(obj, color, grow)
        if obj.type in (OBJ_POLY, OBJ_SMD_PAD):
            return self.poly(obj, BACKGROUND if obj.cutoff and not grow else color, grow)
        if obj.type == OBJ_CIRCLE:
            return self.circle(obj, color, grow)
        if obj.type == OBJ_THT_PAD:
            return self.pad(obj, color, grow)
        if obj.type == OBJ_TEXT:
            # В v6 у текста есть флаг «показывать», в v5 этот байт не заполнен
            if self.version >= 6 and obj.shape == 1 and not obj.flag:
                return ""
            return "".join(self.draw(child, color, grow) for child in obj.children)
        return ""


def render_svg(lay, board_index=0):
    """SVG платы в миллиметрах; каждый слой — отдельная группа <g data-layer>."""
    board = lay.boards[board_index]
    b = _SvgBuilder(lay)
    groups = []
    for code in DRAW_ORDER:
        layer_id, label, color = LAYERS[code]
        on_layer = [o for o in board.objects if o.layer == code and not (o.type == OBJ_THT_PAD and o.plated)]
        body = []
        if code in GROUND_COLORS and board.ground_planes[code - 1]:
            body.append(f'<rect class="ground" fill="{GROUND_COLORS[code]}"/>')
            for o in board.objects:
                if (o.layer == code or o.plated) and o.ground_distance > 0:
                    body.append(b.draw(o, BACKGROUND, grow=o.ground_distance * b.k * 2))
        body.extend(b.draw(o, color) for o in on_layer)
        if not any(body):
            continue
        groups.append(f'<g data-layer="{layer_id}" data-label="{escape(label)}" data-color="{color}">'
                      + "".join(body) + "</g>")

    plated = [o for o in board.objects if o.type == OBJ_THT_PAD and o.plated]
    if plated:
        groups.append(f'<g data-layer="M" data-label="Металлизация" data-color="{METAL_COLOR}">'
                      + "".join(b.pad(o, METAL_COLOR) for o in plated) + "</g>")
    drills = [b.drill(o) for o in board.objects if o.type == OBJ_THT_PAD]
    if any(drills):
        groups.append(f'<g data-layer="D" data-label="Отверстия" data-color="#3a3a3a" fill="{BACKGROUND}">'
                      + "".join(drills) + "</g>")

    if b.min_x is math.inf:
        b.min_x = b.min_y = 0.0
        b.max_x, b.max_y = board.size_x * b.k, board.size_y * b.k
    margin = 2.0
    x, y = b.min_x - margin, b.min_y - margin
    w, h = b.max_x - b.min_x + 2 * margin, b.max_y - b.min_y + 2 * margin
    n = b.num
    content = "".join(groups).replace(
        '<rect class="ground"', f'<rect class="ground" x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{n(x)} {n(y)} {n(w)} {n(h)}" '
        f'width="{n(w)}mm" height="{n(h)}mm" data-board="{escape(board.name)}">'
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" fill="{BACKGROUND}"/>'
        f'<g class="board">{content}</g></svg>'
    )


@lru_cache(maxsize=32)
def _render_cached(path, mtime, size):
    with open(path, "rb") as fh:
        return render_svg(parse(fh.read()))


def render_file(path):
    """SVG для файла на диске; кэшируется до изменения файла."""
    import os

    st = os.stat(path)
    return _render_cached(str(path), st.st_mtime_ns, st.st_size)
