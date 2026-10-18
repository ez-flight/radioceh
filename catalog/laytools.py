"""Анализ плат Sprint Layout: цепи (с перемычками), сводка, проверка (DRC), сравнение версий.

Координаты внутри — миллиметры файла (ось Y вверх). Для показа пользователю переводим в
координаты просмотрщика: x, -y.
"""
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from catalog import lay

COPPER_LAYERS = {1: "Медь, верх", 3: "Медь, низ", 5: "Внутренний 1", 6: "Внутренний 2"}
JUMPER_TOLERANCE = 0.3       # мм: конец линии маркировки на центре площадки
DEFAULT_CLEARANCE = 0.3
DEFAULT_MIN_WIDTH = 0.25
DEFAULT_MIN_RING = 0.15
DEFAULT_EDGE = 0.3           # мм: медь не ближе к краю платы и вырезам (слой Ф)
WIRE_LENGTH = 15.0           # мм: перемычка длиннее — это уже провод
MAX_ISSUES = 60


def object_geometry(o, unit):
    """Медь объекта как фигура shapely в мм (без текста)."""
    k = 1.0 / unit
    t = o.type
    if t == lay.OBJ_LINE and o.points:
        pts = [(x * k, y * k) for x, y in o.points]
        w = max(o.line_width * k, 0.05)
        g = LineString(pts) if len(pts) > 1 else Point(pts[0])
        return g.buffer(w / 2, quad_segs=6)
    if t == lay.OBJ_THT_PAD:
        r = abs(o.out) * k
        x, y = o.x * k, o.y * k
        s = o.shape if 1 <= o.shape <= 9 else 1
        base, stretch = (s - 1) % 3, (s - 1) // 3
        hx = r * (2 if stretch == 1 else 1)
        hy = r * (2 if stretch == 2 else 1)
        if base == 2:
            return box(x - hx, y - hy, x + hx, y + hy)
        if base == 1:
            c = r * (1 - math.tan(math.pi / 8))
            return Polygon([(x - hx + c, y - hy), (x + hx - c, y - hy), (x + hx, y - hy + c), (x + hx, y + hy - c),
                            (x + hx - c, y + hy), (x - hx + c, y + hy), (x - hx, y + hy - c), (x - hx, y - hy + c)])
        if stretch == 0:
            return Point(x, y).buffer(r, quad_segs=8)
        return LineString([(x - (hx - r), y - (hy - r)), (x + (hx - r), y + (hy - r))]).buffer(r, quad_segs=8)
    if t in (lay.OBJ_POLY, lay.OBJ_SMD_PAD) and len(o.points) >= 3:
        g = Polygon([(x * k, y * k) for x, y in o.points]).buffer(0)
        if t == lay.OBJ_POLY and 0 < o.line_width * k < 20:
            g = g.buffer(o.line_width * k / 2, quad_segs=6)
        return g
    if t == lay.OBJ_CIRCLE:
        ro, ri = abs(o.out) * k, abs(o.inner) * k
        rad, w = (ro + ri) / 2, abs(ro - ri)
        angle_k = 1.0 if unit < 1000 else 1000.0
        a0, a1 = (o.start_angle / angle_k) % 360, (o.line_width / angle_k) % 360
        span = 360 if math.isclose(a0, a1) else (a1 - a0) % 360
        n = max(8, int(span / 6))
        pts = [(o.x * k + rad * math.cos(math.radians(a0 + span * i / n)),
                o.y * k + rad * math.sin(math.radians(a0 + span * i / n))) for i in range(n + 1)]
        return LineString(pts).buffer(max(w, 0.05) / 2, quad_segs=6)
    return None


def plural(n, one, few, many):
    """Русское окончание: 1 кусок, 2 куска, 5 кусков."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def is_hole(o):
    """Выводная площадка с отверстием не меньше её самой — отверстие без меди (крепёж, ось)."""
    return o.type == lay.OBJ_THT_PAD and o.inner and abs(o.inner) >= abs(o.out) * 0.999


def pad_center(o):
    """Центр площадки в единицах файла. У SMD поля x, y — мусор, центр считается по углам."""
    if o.type == lay.OBJ_SMD_PAD and o.points:
        return (sum(p[0] for p in o.points) / len(o.points), sum(p[1] for p in o.points) / len(o.points))
    return o.x, o.y


def board_copper_sides(objects):
    """Слои меди, на которых есть дорожки, заливки, SMD или дуги (без выводных площадок)."""
    sides = sorted({o.layer for o in objects if o.type != lay.OBJ_THT_PAD and o.layer in COPPER_LAYERS})
    return tuple(sides) or (3,)


def _copper_layers(o, sides=(3,)):
    """Выводная площадка в Sprint сквозная: она есть на всех слоях меди платы, а её байт «слой»
    медь не задаёт (на двусторонних платах там встречается 2). Остальные объекты — на своём слое."""
    if is_hole(o):
        return ()
    if o.type == lay.OBJ_THT_PAD:
        return sides
    return (o.layer,) if o.layer in COPPER_LAYERS else ()


def find_jumpers(objects, unit):
    """Перемычки: двухточечные линии не на меди, оба конца на центрах выводных площадок."""
    k = 1.0 / unit
    pads = [(o.index, o.x * k, o.y * k) for o in objects if o.type == lay.OBJ_THT_PAD]
    if not pads:
        return []
    tree = STRtree([Point(x, y) for _, x, y in pads])

    def pad_at(x, y):
        hits = tree.query(Point(x, y).buffer(JUMPER_TOLERANCE))
        best = min(hits, key=lambda i: math.hypot(pads[i][1] - x, pads[i][2] - y), default=None)
        if best is None or math.hypot(pads[best][1] - x, pads[best][2] - y) > JUMPER_TOLERANCE:
            return None
        return pads[best][0]

    out = []
    for o in objects:
        if o.type == lay.OBJ_LINE and o.layer not in COPPER_LAYERS and len(o.points) == 2:
            (x1, y1), (x2, y2) = o.points
            a, b = pad_at(x1 * k, y1 * k), pad_at(x2 * k, y2 * k)
            if a is not None and b is not None and a != b:
                out.append((o.index, a, b, math.hypot(x2 - x1, y2 - y1) * k))
    return out


@dataclass
class Issue:
    kind: str
    text: str
    x: float = 0.0       # мм файла
    y: float = 0.0


@dataclass
class Analysis:
    nets: dict = field(default_factory=dict)          # индекс объекта -> номер цепи (1..N)
    net_count: int = 0
    jumpers: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    issue_counts: dict = field(default_factory=dict)

    @property
    def markers(self):
        return [(i.x, i.y, i.text) for i in self.issues]


class _DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p.setdefault(x, x)
        while p != self.p.setdefault(p, p):
            self.p[x] = p = self.p[p]
        return p

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def compute_nets(lay_file, board_index=0):
    """Цепи по геометрии меди с учётом металлизации и перемычек. Возвращает (nets, jumpers, shapes)."""
    board = lay_file.boards[board_index]
    unit = lay_file.unit
    shapes = []          # (индекс, слой, геометрия)
    sides = board_copper_sides(board.objects)
    for o in board.objects:
        layers = _copper_layers(o, sides)
        if not layers:
            continue
        g = object_geometry(o, unit)
        if g is None or g.is_empty:
            continue
        for layer in layers:
            shapes.append((o.index, layer, g))
    dsu = _DSU()
    for idx, _, _ in shapes:
        dsu.find(idx)
    by_layer = defaultdict(list)
    for item in shapes:
        by_layer[item[1]].append(item)
    for items in by_layer.values():
        geoms = [g for _, _, g in items]
        tree = STRtree(geoms)
        for i, (idx, _, g) in enumerate(items):
            for j in tree.query(g, predicate="intersects"):
                if j > i:
                    dsu.union(idx, items[j][0])
    jumpers = find_jumpers(board.objects, unit)
    for line_idx, a, b, _ in jumpers:
        if a in dsu.p and b in dsu.p:
            dsu.union(a, b)
            dsu.union(line_idx, a)
    roots, nets = {}, {}
    for idx in sorted(dsu.p):
        r = dsu.find(idx)
        nets[idx] = roots.setdefault(r, len(roots) + 1)
    return nets, jumpers, shapes


def board_outline(lay_file, board_index=0):
    """Плата по контуру слоя Ф: многоугольник внутри линий контура, вырезы и отверстия без меди — дырами.

    None, если контура нет или он не замкнут.
    """
    board = lay_file.boards[board_index]
    unit = lay_file.unit
    strokes = [object_geometry(o, unit) for o in board.objects if o.layer == 7 and o.type != lay.OBJ_TEXT]
    strokes = [g for g in strokes if g is not None and not g.is_empty]
    if not strokes:
        return None
    lines = unary_union(strokes)
    x0, y0, x1, y1 = lines.bounds
    frame = box(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
    rest = frame.difference(lines)
    inside = [p for p in getattr(rest, "geoms", [rest])
              if p.geom_type == "Polygon" and not p.exterior.intersects(frame.exterior)]
    if not inside:
        return None
    plate = max(inside, key=lambda p: p.area)
    holes = [object_geometry(o, unit) for o in board.objects if is_hole(o)]
    holes = [g for g in holes if g is not None and plate.intersects(g)]
    return plate.difference(unary_union(holes)) if holes else plate


def _summary(lay_file, board, nets, jumpers):
    unit = lay_file.unit
    k = 1.0 / unit
    objs = board.objects
    outline = [object_geometry(o, unit) for o in objs if o.layer == 7 and o.type != lay.OBJ_TEXT]
    outline = [g for g in outline if g is not None]
    if outline:
        xs0, ys0, xs1, ys1 = zip(*(g.bounds for g in outline))
        size = (max(xs1) - min(xs0), max(ys1) - min(ys0))
    else:
        size = (board.size_x * k, board.size_y * k)
    drills = Counter(round(abs(o.inner) * k * 2, 1) for o in objs if o.type == lay.OBJ_THT_PAD and o.inner)
    tracks = [o for o in objs if o.type == lay.OBJ_LINE and o.layer in COPPER_LAYERS]
    sides = board_copper_sides(objs)
    copper_sides = sorted({layer for o in objs for layer in _copper_layers(o, sides)})
    parts = {o.groups[-1] for o in objs if o.groups and o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD)}
    labels = Counter(o.text.strip() for o in objs
                     if o.type == lay.OBJ_TEXT and o.layer not in COPPER_LAYERS and o.text.strip())
    return {
        "name": board.name,
        "version": lay_file.version,
        "size_mm": (round(size[0], 1), round(size[1], 1)),
        "copper_layers": [COPPER_LAYERS[c] for c in copper_sides],
        "tht_pads": sum(1 for o in objs if o.type == lay.OBJ_THT_PAD),
        "smd_pads": sum(1 for o in objs if o.type == lay.OBJ_SMD_PAD),
        "drills": sorted(drills.items()),
        "tracks": len(tracks),
        "polygons": sum(1 for o in objs if o.type == lay.OBJ_POLY and o.layer in COPPER_LAYERS),
        "jumpers": len(jumpers),
        "jumper_length_mm": round(sum(j[3] for j in jumpers), 1),
        "wires": sum(1 for j in jumpers if j[3] > WIRE_LENGTH),
        "holes": sum(1 for o in objs if is_hole(o)),
        "components": len(parts),
        "nets": len(set(nets.values())),
        "labels": sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))[:40],
    }


def _drc(lay_file, board, nets, shapes, clearance, min_width, min_ring, edge=DEFAULT_EDGE, outline=None):
    unit = lay_file.unit
    k = 1.0 / unit
    issues = []
    counts = Counter()

    def add(kind, text, x, y):
        counts[kind] += 1
        if len(issues) < MAX_ISSUES:
            issues.append(Issue(kind, text, round(x, 2), round(y, 2)))

    by_layer = defaultdict(list)
    for idx, layer, g in shapes:
        by_layer[layer].append((idx, g))
    seen = set()
    for layer, items in by_layer.items():
        geoms = [g for _, g in items]
        tree = STRtree(geoms)
        for i, (idx, g) in enumerate(items):
            for j in tree.query(g.buffer(clearance)):
                if j <= i:
                    continue
                jdx = items[j][0]
                if nets.get(idx) == nets.get(jdx):
                    continue
                d = g.distance(geoms[j])
                if d < clearance - 1e-3:
                    key = (min(nets[idx], nets[jdx]), max(nets[idx], nets[jdx]), round(g.centroid.x), round(g.centroid.y))
                    if key in seen:
                        continue
                    seen.add(key)
                    p = g.buffer(clearance).intersection(geoms[j]).representative_point()
                    add("clearance", f"Зазор {d:.2f} мм между разными цепями", p.x, p.y)
    for o in board.objects:
        if o.type == lay.OBJ_LINE and o.layer in COPPER_LAYERS and o.points:
            w = o.line_width * k
            if 0 < w < min_width - 1e-3:
                x, y = o.points[0]
                add("width", f"Дорожка {w:.2f} мм — тоньше {min_width} мм", x * k, y * k)
        if o.type == lay.OBJ_THT_PAD and o.inner and not is_hole(o):
            ring = (abs(o.out) - abs(o.inner)) * k
            if ring < min_ring - 1e-3:
                add("ring", f"Поясок площадки {ring:.2f} мм — меньше {min_ring} мм", o.x * k, o.y * k)
    members = Counter(nets.values())
    for o in board.objects:
        if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD) and o.index in nets and members[nets[o.index]] == 1:
            x, y = pad_center(o)
            add("single", "Площадка ни с чем не соединена", x * k, y * k)
    # медь, в цепи которой нет ни одной площадки: обрывки старых дорожек, островки заливки
    with_pads = {nets[o.index] for o in board.objects
                 if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD) and o.index in nets}
    reported = set()
    for idx, _, g in shapes:
        n = nets.get(idx)
        if n is not None and n not in with_pads and n not in reported:
            reported.add(n)
            p = g.representative_point()
            add("orphan", "Медь ни с чем не соединена (нет площадок)", p.x, p.y)
    # медь у края платы и у вырезов/отверстий
    if outline is not None and edge > 0:
        inner = outline.buffer(-edge)
        seen_edge = set()
        for idx, _, g in shapes:
            if idx in seen_edge or inner.contains(g):
                continue
            out = g.difference(inner)
            if out.area > 0.01:
                seen_edge.add(idx)
                p = out.representative_point()
                add("edge", f"Медь ближе {edge} мм к краю платы или вырезу", p.x, p.y)
    return issues, dict(counts)


def analyze(lay_file, board_index=0, clearance=DEFAULT_CLEARANCE, min_width=DEFAULT_MIN_WIDTH,
            min_ring=DEFAULT_MIN_RING, edge=DEFAULT_EDGE):
    board = lay_file.boards[board_index]
    nets, jumpers, shapes = compute_nets(lay_file, board_index)
    for line_idx, a, _, _ in jumpers:
        nets[line_idx] = nets[a]
    issues, counts = _drc(lay_file, board, nets, shapes, clearance, min_width, min_ring,
                          edge=edge, outline=board_outline(lay_file, board_index))
    return Analysis(nets=nets, net_count=len(set(nets.values())), jumpers=jumpers,
                    summary=_summary(lay_file, board, nets, jumpers), issues=issues, issue_counts=counts)


@lru_cache(maxsize=16)
def _analyze_cached(path, mtime, size):
    with open(path, "rb") as fh:
        return analyze(lay.parse(fh.read()))


def analyze_file(path):
    """Анализ файла на диске; кэшируется до изменения файла."""
    st = os.stat(path)
    return _analyze_cached(str(path), st.st_mtime_ns, st.st_size)


ISSUE_TITLES = {
    "clearance": "Малый зазор",
    "width": "Тонкая дорожка",
    "ring": "Узкий поясок",
    "single": "Неподключённая площадка",
    "orphan": "Медь без площадок",
    "edge": "Медь у края платы",
}


# ------------------------------------------------------------ сравнение версий
@dataclass
class Diff:
    matched: int
    only_a: int
    only_b: int
    splits: list            # [(x, y, текст)]
    merges: list


def _pad_keys(lay_file, board_index=0):
    k = 1.0 / lay_file.unit
    out = {}
    for o in lay_file.boards[board_index].objects:
        if o.type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD):
            x, y = (v * k for v in pad_center(o))
            out[(o.type, o.layer, round(x / 0.05), round(y / 0.05))] = (o.index, x, y)
    return out


def diff(a, b):
    """Что изменилось в соединениях площадок, которые есть в обеих версиях."""
    pa, pb = _pad_keys(a), _pad_keys(b)
    na, _, _ = compute_nets(a)
    nb, _, _ = compute_nets(b)
    common = [key for key in pa if key in pb]
    a_to_b, b_to_a = defaultdict(set), defaultdict(set)
    where = {}
    for key in common:
        ia, x, y = pa[key]
        ib = pb[key][0]
        if ia in na and ib in nb:
            a_to_b[na[ia]].add(nb[ib]); b_to_a[nb[ib]].add(na[ia])
            where.setdefault(("a", na[ia]), (x, y)); where.setdefault(("b", nb[ib]), (x, y))
    splits = [(*where[("a", n)], f"Цепь разделилась на {len(v)} части") for n, v in a_to_b.items() if len(v) > 1]
    merges = [(*where[("b", n)], f"Слились {len(v)} разные цепи") for n, v in b_to_a.items() if len(v) > 1]
    return Diff(matched=len(common), only_a=len(pa) - len(common), only_b=len(pb) - len(common),
                splits=splits, merges=merges)


# ------------------------------------------------------------ сверка со списком соединений
@dataclass
class NetCheck:
    nets: int                  # цепей в списке
    ok: int                    # собраны в один кусок и ни с чем не слиты
    broken: list               # [(цепь, [[метки куска], …])]
    shorts: list               # [(цепь, цепь, метка)] — разные цепи списка на одной меди
    missing: list              # [(цепь, метка, x, y, причина)] — точка не на меди или на нескольких цепях

    @property
    def passed(self):
        return not (self.broken or self.shorts or self.missing)


def _locator(lay_file, board_index=0):
    nets, _, shapes = compute_nets(lay_file, board_index)
    objs = lay_file.boards[board_index].objects
    geoms = [g for _, _, g in shapes]
    tree = STRtree(geoms) if geoms else None

    def at(x, y):
        """Множество цепей меди в точке; выводные и SMD-площадки важнее дорожек и заливки."""
        if tree is None:
            return set()
        p = Point(x, y)
        hits = [i for i in tree.query(p.buffer(0.05)) if geoms[i].distance(p) < 0.05]
        pads = [i for i in hits if objs[shapes[i][0]].type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD)]
        return {nets[shapes[i][0]] for i in (pads or hits)}
    return at


def check_netlist(lay_file, netlist, board_index=0):
    """netlist: {цепь: [(x, y, метка), …]} в мм файла (ось Y вверх). Каждая цепь должна быть одним
    куском меди (с учётом перемычек), и разные цепи не должны сходиться на одной меди."""
    at = _locator(lay_file, board_index)
    broken, shorts, missing, owner = [], [], [], {}
    for name, points in netlist.items():
        pieces = defaultdict(list)
        for x, y, label in points:
            found = at(x, y)
            if len(found) != 1:
                missing.append((name, label, x, y, "нет меди" if not found else "на нескольких цепях"))
                continue
            pieces[found.pop()].append(label)
        if len(pieces) > 1:
            broken.append((name, list(pieces.values())))
        for cid, labels in pieces.items():
            if cid in owner and owner[cid] != name:
                shorts.append((owner[cid], name, labels[0]))
            owner.setdefault(cid, name)
    bad = {b[0] for b in broken} | {m[0] for m in missing} | {s[0] for s in shorts} | {s[1] for s in shorts}
    ok = sum(1 for name in netlist if name not in bad)
    return NetCheck(nets=len(netlist), ok=ok, broken=broken, shorts=shorts, missing=missing)


def export_netlist(lay_file, board_index=0):
    """Список соединений платы по площадкам: [(цепь, x, y, метка)] в мм файла. Цепи из одной площадки
    пропускаются. Служит эталоном: после правок платы её можно сверить с ним (check_netlist)."""
    nets, _, _ = compute_nets(lay_file, board_index)
    k = 1.0 / lay_file.unit
    rows = []
    for o in lay_file.boards[board_index].objects:
        if o.type not in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD) or o.index not in nets:
            continue
        x, y = (v * k for v in pad_center(o))
        rows.append((nets[o.index], round(x, 3), round(y, 3), f"#{o.index}"))
    sizes = Counter(r[0] for r in rows)
    return [(f"N{n}", x, y, label) for n, x, y, label in rows if sizes[n] > 1]


# ------------------------------------------------------------ готовые SVG для сайта (с кэшем)
@lru_cache(maxsize=16)
def _svg_cached(path, mtime, size, with_markers):
    with open(path, "rb") as fh:
        lay_file = lay.parse(fh.read())
    a = _analyze_cached(path, mtime, size)
    return lay.render_svg(lay_file, nets=a.nets, markers=a.markers if with_markers else None)


def svg_with_nets(path, with_markers=False):
    st = os.stat(path)
    return _svg_cached(str(path), st.st_mtime_ns, st.st_size, bool(with_markers))


@lru_cache(maxsize=16)
def _print_cached(path, mtime, size, layer, mirror):
    with open(path, "rb") as fh:
        return lay.render_print_svg(lay.parse(fh.read()), layer=layer, mirror=mirror)


def print_svg(path, layer, mirror):
    st = os.stat(path)
    return _print_cached(str(path), st.st_mtime_ns, st.st_size, int(layer), bool(mirror))
