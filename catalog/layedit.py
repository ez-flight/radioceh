"""Побайтовое чтение и запись файла Sprint Layout (одна плата) для правки объектов.

Поддержаны версии 5 и 6; блок компонента lay6 у текста переносится без разбора.
Чтение+запись без правок даёт исходный файл байт в байт.
"""
import struct

HDR = 77


class Obj:
    def __init__(self, hdr, text=b"", marker=b"", groups=(), points=None, children=None, toplevel=True):
        self.hdr = bytearray(hdr)
        self.text, self.marker, self.groups = text, marker, list(groups)
        self.points = points          # для линий/полигонов/SMD
        self.children = children      # для текста
        self.toplevel = toplevel

    # поля заголовка
    type = property(lambda s: s.hdr[0])
    layer = property(lambda s: s.hdr[22])

    def get(self, fmt, off):
        return struct.unpack_from(fmt, self.hdr, off)[0]

    def set(self, fmt, off, value):
        struct.pack_into(fmt, self.hdr, off, value)

    @property
    def xy(self):
        return self.get("<f", 1), self.get("<f", 5)

    def move(self, dx, dy):
        x, y = self.xy
        self.set("<f", 1, x + dx)
        self.set("<f", 5, y + dy)
        if self.points is not None:
            self.points = [(px + dx, py + dy) for px, py in self.points]
        for c in self.children or []:
            c.move(dx, dy)

    def to_bytes(self):
        out = bytearray(self.hdr)
        if self.toplevel:
            for s in (self.text, self.marker):
                out += struct.pack("<I", len(s)) + s
            out += struct.pack("<I", len(self.groups)) + b"".join(struct.pack("<I", g) for g in self.groups)
        if self.type == 5:
            return bytes(out)
        if self.type == 7:
            out += struct.pack("<I", len(self.children)) + b"".join(c.to_bytes() for c in self.children)
            return bytes(out) + getattr(self, "comp", b"")
        out += struct.pack("<I", len(self.points)) + b"".join(struct.pack("<ff", *p) for p in self.points)
        return bytes(out)


def _read_obj(data, pos, toplevel=True):
    hdr = data[pos:pos + HDR]; pos += HDR
    text = marker = b""; groups = ()
    if toplevel:
        n = struct.unpack_from("<I", data, pos)[0]; pos += 4; text = data[pos:pos + n]; pos += n
        n = struct.unpack_from("<I", data, pos)[0]; pos += 4; marker = data[pos:pos + n]; pos += n
        n = struct.unpack_from("<I", data, pos)[0]; pos += 4
        groups = struct.unpack_from(f"<{n}I", data, pos); pos += 4 * n
    kind = hdr[0]
    if kind == 5:
        return Obj(hdr, text, marker, groups, toplevel=toplevel), pos
    if kind == 7:
        n = struct.unpack_from("<I", data, pos)[0]; pos += 4
        children = []
        for _ in range(n):
            c, pos = _read_obj(data, pos, toplevel=False)
            children.append(c)
        comp = b""
        if hdr[23] == 1 and data[0] >= 6 and toplevel:
            # блок компонента v6: f32, f32, u8, f64, строка корпуса, строка комментария, u8 — переносится как есть
            start = pos; pos += 17
            for _ in range(2):
                pos += 4 + struct.unpack_from("<I", data, pos)[0]
            pos += 1
            comp = data[start:pos]
        o = Obj(hdr, text, marker, groups, children=children, toplevel=toplevel)
        o.comp = comp
        return o, pos
    n = struct.unpack_from("<I", data, pos)[0]; pos += 4
    pts = [struct.unpack_from("<ff", data, pos + 8 * i) for i in range(n)]; pos += 8 * n
    return Obj(hdr, text, marker, groups, points=pts, toplevel=toplevel), pos


ROUND, OCTAGON, SQUARE = 1, 2, 3          # формы выводных площадок


def pad_points(shape, x, y, r):
    """Точки выводной площадки, как их пишет Sprint: по ним он рисует медь площадки, а без точек Sprint 6
    не открывает файл. Круг — отрезок-диаметр, квадрат — 4 угла, восьмиугольник — 8 вершин;
    формы 4–9 вытянуты вдвое по X (4–6) или по Y (7–9)."""
    base, stretch = (shape - 1) % 3, (shape - 1) // 3
    sx, sy = (2, 1) if stretch == 1 else (1, 2) if stretch == 2 else (1, 1)
    if base == 0:
        return [(x + r, y), (x - r, y)] if stretch != 2 else [(x, y + r), (x, y - r)]
    hx, hy = r * sx, r * sy
    if base == 2:
        return [(x - hx, y + hy), (x + hx, y + hy), (x + hx, y - hy), (x - hx, y - hy)]
    c = r * (2 ** 0.5 - 1)                 # полсторона восьмиугольника
    ex, ey = hx - r + c, hy - r + c
    return [(x - hx, y + ey), (x - ex, y + hy), (x + ex, y + hy), (x + hx, y + ey),
            (x + hx, y - ey), (x + ex, y - hy), (x - ex, y - hy), (x - hx, y - ey)]

# Заголовки объектов, сохранённые самим Sprint Layout (v5 — _341_v2.lay, v6 — TA2003P…lay6). Новый объект
# берёт заголовок у объекта того же типа из правимого файла, а если такого нет — отсюда; координаты,
# размеры и слой перезаписываются, неизвестные поля остаются как у Sprint.
TEMPLATES = {
    5: {
        2: "0210c390444b669bc50000c84200001c4276a201a800030178936c0700000055000000cc936c07003128000000b8936c070000000064000000000100000015cd5b070000000000000000000000",
        4: "048a258c45004012c5b0e0404a8a0be04e0000000000030520f640070000000080f1c4e0f64007051028000000ccf64007000001000a000000000032350015cd5b0700001b0000000000000002",
        5: "0500406e44001038c50000424300001a435a000000000201000000000000000e01000058a76c0700002800000044a76c07000000000000000000000002000000303000007014560070145600f4",
        6: "0600c0a84400c8b4c530302e30300000584100000000030328b96c07000000001300008cb96c0700022800000048b96c07003d0300ea3d032c020000004b030288ea3d0388ea3d031c02000088",
        8: "080090114600d890c500007a430000af43374103ec000303f8ba6c070000000017000064bb6c0700062800000050bb6c0700000000384103103801039805000010000000130000000000000002",
    },
    6: {
        2: "02000a254800a34ac800401c4600401c4500000000000301903fb003000000555555552040b0030000a00f0000f03fb0030000000064000000000100000015cd5b070000000000000000000000",
        4: "0400000000000000000000000000000000a00f000000030098fd900300000000000000c8fd90030000881300000000000000000100a00f00000000000000000000000000000000000000000000",
        5: "0500e6aa48008ff7c80010244600701446b01e040000030000000000000000b01e04004007f1050000a00f00000000000000000000000000000000000000000000000000000000000000000000",
        6: "0600000000000000000000000000000000a00f00000003005042910300000000000000204291030000a00f00000000000000000000000000000000000000000000000000000000000000000000",
        8: "08000000000000000000803b4600c05a4656a102c4000302904a910300000055000000484a91030000a00f0000304a91030000320064000000200100000015cd5b070000000000000000000000",
    },
}


class LayDoc:
    COUNT_OFF = 0x21A  # версия 5, одна плата: число объектов сразу после заголовка платы

    def __init__(self, data):
        if data[1:4] != b"\x33\xaa\xff" or data[0] not in (5, 6) or struct.unpack_from("<I", data, 4)[0] != 1:
            raise ValueError("Нужен файл Sprint Layout 5/6 с одной платой")
        self.prefix = data[:self.COUNT_OFF]
        n = struct.unpack_from("<I", data, self.COUNT_OFF)[0]
        pos = self.COUNT_OFF + 4
        self.objects = []
        for _ in range(n):
            o, pos = _read_obj(data, pos)
            self.objects.append(o)
        for o in self.objects:
            if o.type in (2, 8):
                k = struct.unpack_from("<I", data, pos)[0]
                if k:
                    raise ValueError("Файлы с непустыми соединениями (ratsnest) не поддержаны")
                pos += 4
        self.trailer = data[pos:]

    # ---------------------------------------------------------------- создание объектов (мм, ось Y вверх)
    @property
    def version(self):
        return self.prefix[0]

    @property
    def unit(self):
        """Единиц файла в миллиметре."""
        return 100.0 if self.version < 6 else 10000.0

    @property
    def angle_unit(self):
        return 1.0 if self.version < 6 else 1000.0

    def _new(self, kind, layer, first=False):
        src = next((o for o in self.objects if o.type == kind and o.toplevel), None)
        hdr = src.hdr if src is not None else bytes.fromhex(TEMPLATES[6 if self.version >= 6 else 5][kind])
        o = Obj(hdr, points=[] if kind not in (5, 7) else None, children=[] if kind == 7 else None)
        o.hdr[0] = kind
        o.hdr[22] = layer
        if first:
            self.objects.insert(0, o)      # рисуется первым — под остальными объектами
        else:
            self.objects.append(o)
        return o

    def _xy(self, o, x, y):
        o.set("<f", 1, x * self.unit)
        o.set("<f", 5, y * self.unit)

    def add_line(self, points, width, layer=3):
        """Дорожка (медь) или линия маркировки/контура: points — [(x, y), …] в мм."""
        o = self._new(6, layer)
        o.points = [(x * self.unit, y * self.unit) for x, y in points]
        self._xy(o, *points[0])
        o.set("<I", 17, int(round(width * self.unit)))
        return o

    def add_pad(self, x, y, diameter, drill, shape=ROUND, layer=3):
        """Выводная площадка; drill >= diameter — отверстие без меди."""
        o = self._new(2, layer)
        self._xy(o, x, y)
        o.points = [(px * self.unit, py * self.unit) for px, py in pad_points(shape, x, y, diameter / 2)]
        o.set("<f", 9, diameter / 2 * self.unit)
        o.set("<f", 13, drill / 2 * self.unit)
        o.hdr[23] = shape
        return o

    def add_smd(self, x, y, w, h, layer=3):
        o = self._new(8, layer)
        u = self.unit
        o.points = [((x - w / 2) * u, (y + h / 2) * u), ((x - w / 2) * u, (y - h / 2) * u),
                    ((x + w / 2) * u, (y - h / 2) * u), ((x + w / 2) * u, (y + h / 2) * u)]
        self._xy(o, x, y)
        return o

    def add_polygon(self, points, layer=3, width=0.0, first=False):
        """Залитый многоугольник без дыр (замыкать не нужно). first=True — в начало списка объектов
        (заливка под площадками, иначе Sprint рисует её поверх и прячет площадки и отверстия)."""
        o = self._new(4, layer, first)
        o.points = [(x * self.unit, y * self.unit) for x, y in points]
        self._xy(o, *points[0])
        o.set("<I", 17, int(round(width * self.unit)))
        return o

    def add_circle(self, x, y, radius, width, layer=7, start=0.0, end=0.0):
        """Окружность (start == end) или дуга, углы в градусах; на слое 7 — фрезеровка (отверстие, вырез)."""
        o = self._new(5, layer)
        self._xy(o, x, y)
        o.set("<f", 9, (radius + width / 2) * self.unit)
        o.set("<f", 13, (radius - width / 2) * self.unit)
        o.set("<I", 31, int(round(start * self.angle_unit)))
        o.set("<I", 17, int(round(end * self.angle_unit)))
        return o

    def add_text(self, text, x, y, height=1.0, layer=2, width=0.15, anchor="left"):
        """Надпись штриховым шрифтом (линиями), кириллица поддерживается."""
        from catalog.layfont import strokes
        return [self.add_line(poly, width, layer) for poly in strokes(text, x, y, height, anchor)]

    def to_bytes(self):
        out = bytearray(self.prefix)
        out += struct.pack("<I", len(self.objects))
        for o in self.objects:
            out += o.to_bytes()
        out += b"\x00\x00\x00\x00" * sum(1 for o in self.objects if o.type in (2, 8))
        out += self.trailer
        return bytes(out)
