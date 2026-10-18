"""Заливка медью (обычно землёй) свободного места на плате Sprint Layout.

Берётся цепь в заданной точке, вокруг чужой меди оставляется зазор, перешейки уже min_neck убираются,
куски, не касающиеся своей цепи, не заливаются (их число и площадь — в отчёте: это будущие островки).
Многоугольники с дырами Sprint не понимает — они режутся на части без дыр.
"""
from dataclasses import dataclass

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from catalog import lay
from catalog.layedit import LayDoc
from catalog.laytools import board_outline, compute_nets, is_hole, object_geometry


@dataclass
class PourReport:
    net: int
    polygons: int           # записано многоугольников (после разрезки дыр)
    area: float             # мм², залито
    pieces: int             # связных кусков заливки
    skipped: int            # кусков, не касающихся цепи (не залиты)
    skipped_area: float


def split_holes(poly):
    """Многоугольник с дырами -> многоугольники без дыр (разрезы по вертикали через дыры)."""
    poly = poly.simplify(0.01)
    if poly.is_empty:
        return []
    if poly.geom_type != "Polygon":
        return [q for g in getattr(poly, "geoms", []) for q in split_holes(g)]
    if not poly.interiors:
        return [poly]
    cx = Polygon(poly.interiors[0]).centroid.x
    minx, miny, maxx, maxy = poly.bounds
    out = []
    for half in (box(minx - 1, miny - 1, cx, maxy + 1), box(cx, miny - 1, maxx + 1, maxy + 1)):
        part = poly.intersection(half)
        for g in getattr(part, "geoms", [part]):
            if g.geom_type == "Polygon" and g.area > 0.01:
                out.extend(split_holes(g))
    return out


def thermal_cut(area, pads, gap=0.4, spoke=0.6):
    """Тепловые барьеры: вокруг площадок своей цепи — кольцевой зазор gap, связь с заливкой четырьмя
    спицами шириной spoke. Площадка остаётся видна и легко паяется."""
    cuts = []
    for g in pads:
        if g is None or g.is_empty or not area.intersects(g.buffer(gap)):
            continue
        c = g.centroid
        x0, y0, x1, y1 = g.buffer(gap + 0.2).bounds
        bars = box(x0, c.y - spoke / 2, x1, c.y + spoke / 2).union(box(c.x - spoke / 2, y0, c.x + spoke / 2, y1))
        cuts.append(g.buffer(gap).difference(g).difference(bars))
    return area.difference(unary_union(cuts)) if cuts else area


def pour(data, at, layer=3, clearance=0.4, edge=0.6, min_neck=0.5, region=None, min_area=1.0,
         thermal=True):
    """data — файл (байты), at — точка (x, y) в мм файла на меди нужной цепи, region — ограничение
    (shapely, мм файла). Многоугольники пишутся в начало списка объектов — под площадки и дорожки.
    Возвращает (новый файл, PourReport)."""
    lay_file = lay.parse(data)
    doc = LayDoc(data)
    nets, _, shapes = compute_nets(lay_file)
    on_layer = [(idx, g) for idx, lyr, g in shapes if lyr == layer]
    p = Point(*at)
    hits = [idx for idx, g in on_layer if g.distance(p) < 0.05]
    if not hits:
        raise ValueError(f"В точке ({at[0]}; {-at[1]}) нет меди на слое {layer}")
    target = nets[hits[0]]
    own = unary_union([g for idx, g in on_layer if nets.get(idx) == target])
    foreign = unary_union([g for idx, g in on_layer if nets.get(idx) != target])

    outline = board_outline(lay_file)
    if outline is not None:
        base = outline.buffer(-edge)
    else:
        base = unary_union([g for _, g in on_layer]).envelope
    if region is not None:
        base = base.intersection(region)
    holes = [object_geometry(o, lay_file.unit) for o in lay_file.boards[0].objects if is_hole(o)]
    keep_out = [foreign.buffer(clearance, quad_segs=6)] + [h.buffer(edge) for h in holes if h is not None]
    area = base.difference(unary_union(keep_out))
    if min_neck > 0:
        area = area.buffer(-min_neck / 2).buffer(min_neck / 2)
    if thermal:
        objs = lay_file.boards[0].objects
        own_pads = [g for idx, g in on_layer
                    if nets.get(idx) == target and objs[idx].type in (lay.OBJ_THT_PAD, lay.OBJ_SMD_PAD)]
        area = thermal_cut(area, own_pads)

    pieces = [g for g in getattr(area, "geoms", [area]) if g.geom_type == "Polygon" and g.area >= min_area]
    linked = [g for g in pieces if g.intersects(own)]
    lonely = [g for g in pieces if not g.intersects(own)]
    written = 0
    for g in linked:
        for part in split_holes(g):
            doc.add_polygon(list(part.exterior.coords)[:-1], layer=layer, first=True)
            written += 1
    report = PourReport(net=target, polygons=written, area=round(sum(g.area for g in linked), 1),
                        pieces=len(linked), skipped=len(lonely), skipped_area=round(sum(g.area for g in lonely), 1))
    return doc.to_bytes(), report
