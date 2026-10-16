#!/usr/bin/env python3
"""Build category + model indexes from saved catalog HTML (names only)."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = Path("/tmp/rw6ase")

CATEGORIES = [
    {
        "code": "detektor",
        "name": "Радиоприёмники детекторные",
        "short_name": "Детекторные",
        "slug": "detektornye",
        "file": "detektor.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_detektor/",
        "sort_order": 1,
    },
    {
        "code": "lamp",
        "name": "Радиоприёмники ламповые стационарные",
        "short_name": "Ламповые стационарные",
        "slug": "lampovye-statsionarnye",
        "file": "lamp.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/",
        "sort_order": 2,
    },
    {
        "code": "ps_suw",
        "name": "Радиоприёмники сувенирные стационарные",
        "short_name": "Сувенирные стационарные",
        "slug": "suvenirnye-statsionarnye",
        "file": "ps_suw.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_ps_suw/",
        "sort_order": 3,
    },
    {
        "code": "lamp_bat",
        "name": "Радиоприёмники ламповые батарейные",
        "short_name": "Ламповые батарейные",
        "slug": "lampovye-batareynye",
        "file": "lamp_bat.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_lamp_bat/",
        "sort_order": 4,
    },
    {
        "code": "transl",
        "name": "Радиоприёмники ламповые и п/п трансляционные",
        "short_name": "Трансляционные",
        "slug": "translyatsionnye",
        "file": "transl.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_transl/",
        "sort_order": 5,
    },
    {
        "code": "pp_suw",
        "name": "Радиоприёмники сувенирные носимые",
        "short_name": "Сувенирные носимые",
        "slug": "suvenirnye-nosimye",
        "file": "pp_suw.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_pp_suw/",
        "sort_order": 6,
    },
    {
        "code": "awto_lamp",
        "name": "Радиоприёмники ламповые для авто",
        "short_name": "Ламповые авто",
        "slug": "lampovye-avto",
        "file": "awto_lamp.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_awto_lamp/",
        "sort_order": 7,
    },
    {
        "code": "ps",
        "name": "Радиоприёмники на п/п стационарные",
        "short_name": "П/п стационарные",
        "slug": "pp-statsionarnye",
        "file": "ps.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_ps/",
        "sort_order": 8,
    },
    {
        "code": "pp",
        "name": "Радиоприёмники на п/п носимые",
        "short_name": "П/п носимые",
        "slug": "pp-nosimye",
        "file": None,
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_pp/",
        "sort_order": 9,
    },
    {
        "code": "awto_pp",
        "name": "Радиоприёмники на п/п для авто",
        "short_name": "П/п авто",
        "slug": "pp-avto",
        "file": "awto_pp.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_awto_pp/",
        "sort_order": 10,
    },
    {
        "code": "rl_ps",
        "name": "Радиолы на п/п стационарные",
        "short_name": "Радиолы п/п",
        "slug": "radioly-pp",
        "file": "rl_ps.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rl_ps/",
        "sort_order": 11,
    },
    {
        "code": "pp_det",
        "name": "Радиоприёмники детские носимые",
        "short_name": "Детские носимые",
        "slug": "detskie-nosimye",
        "file": "pp_det.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/rp_pp_det/",
        "sort_order": 12,
    },
    {
        "code": "rl_lamp",
        "name": "Радиолы ламповые стационарные",
        "short_name": "Радиолы ламповые",
        "slug": "radioly-lampovye",
        "file": "rl_lamp.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/",
        "sort_order": 13,
    },
    {
        "code": "tuner",
        "name": "Тюнеры на п/п стационарные",
        "short_name": "Тюнеры п/п",
        "slug": "tunery-pp",
        "file": "tuner.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/tjuner_ps/",
        "sort_order": 14,
    },
    {
        "code": "efir",
        "name": "Эфирные радиоточки на п/п",
        "short_name": "Эфирные радиоточки",
        "slug": "efirnye-radiotochki",
        "file": "efir.html",
        "base": "https://rw6ase.narod.ru/index1/radiopriem/efir_r_toch/",
        "sort_order": 15,
    },
    {
        "code": "konstr",
        "name": "Радиоконструкторы",
        "short_name": "Радиоконструкторы",
        "slug": "radiokonstruktory",
        "file": "konstr_radiopriem.html",
        "base": "https://rw6ase.narod.ru/index1/konstr/rk_radiopriem/",
        "sort_order": 16,
    },
]

SKIP_NAME = {
    "",
    "детекторы",
    "на стартовую страницу сайта",
    "ещё детские приёмники есть в радиоконструкторах",
}
SKIP_HREF = re.compile(
    r"(narod\.ru/?$|index0/|konstr/|_radiopriem\.html|\.gif$|\.jpg$|\.png$)",
    re.I,
)
LINK_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def decode(raw: bytes) -> str:
    # Some index pages are UTF-8; decoding them as cp1251 produces
    # names like "Р Р°РґРёРѕС‚РµС…РЅРёРєР°" instead of "Радиотехника".
    utf8 = None
    cp1251 = None
    try:
        utf8 = raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        cp1251 = raw.decode("cp1251")
    except UnicodeDecodeError:
        pass
    if utf8 is not None and (
        "charset=utf-8" in utf8.lower() or "charset=\"utf-8\"" in utf8.lower()
    ):
        return utf8
    if utf8 is not None and cp1251 is not None:
        moji = ("Р°", "Рґ", "С‚", "С…", "Р Р")
        score = lambda s: sum(s.count(m) for m in moji)
        return utf8 if score(utf8) <= score(cp1251) else cp1251
    return utf8 or cp1251 or raw.decode("cp1251", errors="replace")


def clean_name(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(text))
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n-–—")
    return text


def parse_page(html: str, base: str) -> list[dict]:
    items = []
    seen = set()
    for href, raw_name in LINK_RE.findall(html):
        href = unescape(href).strip()
        name = clean_name(raw_name)
        if SKIP_HREF.search(href):
            continue
        filename = href.rsplit("/", 1)[-1].split("?")[0]
        if filename.startswith("_") or not filename.lower().endswith(".html"):
            continue
        if name.lower() in SKIP_NAME or len(name) < 2:
            continue
        key = (name.lower(), href.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append({"name": name, "path": href, "source_url": urljoin(base, href)})
    return items


def main() -> None:
    DATA.mkdir(exist_ok=True)
    catalog = []
    portable = json.loads((DATA / "catalog_index.json").read_text(encoding="utf-8"))
    for item in portable:
        catalog.append(
            {
                "name": item["name"],
                "category": "pp",
                "path": item.get("path", ""),
                "source_url": item.get("source_url", ""),
            }
        )

    for cat in CATEGORIES:
        if not cat["file"]:
            continue
        path = SRC / cat["file"]
        if not path.exists():
            path = DATA / cat["file"]
        if not path.exists():
            continue
        html = decode(path.read_bytes())
        for item in parse_page(html, cat["base"]):
            catalog.append({**item, "category": cat["code"]})

    (DATA / "categories.json").write_text(
        json.dumps(
            [
                {k: v for k, v in cat.items() if k not in {"file", "base"}}
                for cat in CATEGORIES
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (DATA / "all_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for item in catalog:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    print("categories", len(CATEGORIES))
    print("models", len(catalog))
    for cat in CATEGORIES:
        print(f"  {cat['code']:12} {counts.get(cat['code'], 0):4}  {cat['name']}")


if __name__ == "__main__":
    main()
