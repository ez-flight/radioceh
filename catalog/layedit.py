"""Побайтовое чтение и запись файла Sprint Layout (одна плата) для правки объектов.

Поддержаны версии 5 и 6 без компонентов lay6 (у текстов v6 с флагом компонента — NotImplementedError).
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
            return bytes(out)
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
        if hdr[23] == 1 and data[0] >= 6:
            raise NotImplementedError("компоненты lay6 не поддержаны")
        return Obj(hdr, text, marker, groups, children=children, toplevel=toplevel), pos
    n = struct.unpack_from("<I", data, pos)[0]; pos += 4
    pts = [struct.unpack_from("<ff", data, pos + 8 * i) for i in range(n)]; pos += 8 * n
    return Obj(hdr, text, marker, groups, points=pts, toplevel=toplevel), pos


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

    def to_bytes(self):
        out = bytearray(self.prefix)
        out += struct.pack("<I", len(self.objects))
        for o in self.objects:
            out += o.to_bytes()
        out += b"\x00\x00\x00\x00" * sum(1 for o in self.objects if o.type in (2, 8))
        out += self.trailer
        return bytes(out)
