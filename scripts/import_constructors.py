#!/usr/bin/env python3
"""Parse rw6ase radio-constructor index and import the category."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX_URL = "https://rw6ase.narod.ru/index1/konstr/rk_radiopriem/_radiopriem.html"
INDEX_FILE = DATA / "konstr_radiopriem.html"
USER_AGENT = "Mozilla/5.0 (compatible; RadiotsekhCatalog/1.0)"

SKIP_HREF = re.compile(
    r"(narod\.ru/?$|index0/|_radiopriem\.html|\.gif$)",
    re.I,
)
SKIP_NAME = {"", "на стартовую страницу сайта"}
NAV_IMG = re.compile(
    r"(lw|pw|ln|pn|rt20|ws|ls|ns|ps|counter|yadro|/stat/)\b",
    re.I,
)
LINK_RE = re.compile(
    r'(?:((?:19|20)\d{2})\s*(?:<[^>]+>\s*)*-{2}\s*(?:<[^>]+>\s*)*)?'
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    r'(?:\s*(?:<[^>]+>\s*)*-?\s*(?:<[^>]+>\s*)*\(([^)]+)\))?',
    re.I | re.S,
)
QUOTED_RE = re.compile(r'"([^"]+)"')


def decode(raw: bytes) -> str:
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
    if utf8 is not None and "charset=utf-8" in utf8.lower():
        return utf8
    if utf8 is not None and cp1251 is not None:
        moji = ("Р°", "Рґ", "С‚", "С…", "Р Р")
        return utf8 if sum(utf8.count(m) for m in moji) <= sum(cp1251.count(m) for m in moji) else cp1251
    return utf8 or cp1251 or raw.decode("cp1251", errors="replace")


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(text))
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip(" \t\r\n-–—")


def display_name(raw_name: str, note: str = "") -> str:
    name = clean_text(raw_name).replace("«", '"').replace("»", '"').replace("''", '"')
    name = re.sub(r"^РК\.\s*", "", name)
    note = clean_text(note)
    if note.lower() in {"рк"}:
        note = ""
    quoted = QUOTED_RE.findall(name)
    extras: list[str] = []
    if quoted:
        core = quoted[0]
        before = re.sub(
            r"^(?:Радиоконструктор|Радиоприёмник|Набор|Радиола|Радиоприставка)\s+",
            "",
            name.split(f'"{quoted[0]}"', 1)[0],
            flags=re.I,
        ).strip(" .")
        if before and "старт" in before.lower() and "парус" in core.lower():
            core = f"Старт «{core}»"
        elif before and re.search(r"№", before):
            core = f"{core} {before}"
        after = name.split(f'"{quoted[-1]}"', 1)[-1].strip(" -–—()")
        if after and after.lower() not in {core.lower(), note.lower()}:
            extras.append(after)
    else:
        core = re.sub(
            r"^Радиоконструктор\s+",
            "",
            name,
            count=1,
            flags=re.I,
        )
        if core.lower() == "старт" or core.lower().startswith("старт "):
            core = core
        elif name.lower().startswith("радиоконструктор"):
            core = name
    if note and note.lower() not in {core.lower(), *(e.lower() for e in extras)}:
        extras.append(note)
    if extras:
        return f"{core} ({', '.join(extras)})"
    return core


def merge_names(names: list[str]) -> str:
    uniq: list[str] = []
    for name in names:
        if name and name.lower() not in {x.lower() for x in uniq}:
            uniq.append(name)
    if not uniq:
        return "Радиоконструктор"
    uniq.sort(key=len, reverse=True)
    kept: list[str] = []
    for name in uniq:
        low = name.lower()
        if any(
            other.lower() != low
            and (
                other.lower().startswith(low + " ")
                or other.lower().startswith(low + "-")
                or other.lower().endswith(" " + low)
            )
            for other in kept + [x for x in uniq if x != name]
        ):
            continue
        kept.append(name)
    kept.sort(key=lambda item: (len(item), item))
    return " / ".join(kept)


def parse_index(html: str) -> list[dict]:
    by_url: dict[str, dict] = {}
    for year, href, raw_name, note in LINK_RE.findall(html):
        href = unescape(href).strip()
        if SKIP_HREF.search(href):
            continue
        filename = href.rsplit("/", 1)[-1].split("?")[0]
        if not filename.lower().endswith(".html"):
            continue
        name = display_name(raw_name, note or "")
        if name.lower() in SKIP_NAME or len(name) < 2:
            continue
        url = urljoin(INDEX_URL, href)
        item = by_url.setdefault(
            url,
            {"names": [], "years": set(), "path": href, "source_url": url},
        )
        if not year:
            item["names"].append(name)
        if year:
            item["years"].add(int(year))
        if note and re.fullmatch(r"(?:19|20)\d{2}", clean_text(note)):
            item["years"].add(int(clean_text(note)))
    rows = []
    for item in by_url.values():
        if not item["names"]:
            continue
        years = sorted(item["years"])
        name = merge_names(item["names"])
        year_start = years[0] if years else None
        year_end = years[-1] if len(years) > 1 else None
        if year_start and year_end and year_end != year_start:
            years_text = f"{year_start}–{year_end}"
        elif year_start:
            years_text = str(year_start)
        else:
            years_text = ""
        rows.append(
            {
                "name": name,
                "category": "konstr",
                "path": item["path"],
                "source_url": item["source_url"],
                "years": years_text,
                "year_start": year_start,
                "year_end": year_end,
            }
        )
    names: dict[str, int] = {}
    for row in rows:
        names[row["name"]] = names.get(row["name"], 0) + 1
    for row in rows:
        if names[row["name"]] > 1 and row["year_start"]:
            stamped = f"{row['name']} ({row['year_start']})"
            if not row["name"].endswith(f"({row['year_start']})"):
                row["name"] = stamped
    rows.sort(key=lambda r: (r["name"].lower(), r.get("year_start") or 0))
    return rows


def extract_description(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    parts: list[str] = []
    for chunk in re.findall(r"<font[^>]*>(.*?)</font>", html, flags=re.I | re.S):
        text = clean_text(chunk)
        if len(text) < 40 or not re.search(r"[А-Яа-яЁё]", text):
            continue
        low = text.lower()
        if low.startswith("страница с") or low.startswith("фотографии"):
            continue
        if text in parts:
            continue
        parts.append(text)
    text = " ".join(parts)
    text = re.sub(r"\s+Инструкция\s+по сборке.*$", "", text)
    text = re.sub(r"\s+Материалы по радиоконструктору.*$", "", text)
    return text[:2500].strip()


FIELD_LIMITS = {
    "sensitivity": 160,
    "selectivity": 160,
    "output_power": 120,
    "frequency_response": 120,
    "power_supply": 160,
    "dimensions": 80,
    "weight": 40,
    "original_price": 80,
}


def clip(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .;")
    if len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value


def extract_specs(text: str) -> dict:
    specs: dict = {}

    def grab(key: str, pattern: str, unit: str | None = None, reject: str | None = None) -> None:
        match = re.search(pattern, text, re.I)
        if not match:
            return
        value = match.group(1).strip(" .;")
        if unit and not re.search(unit, value, re.I):
            return
        if reject and re.search(reject, value):
            return
        specs[key] = clip(value, FIELD_LIMITS[key])

    grab("sensitivity", r"чувствительност[ьи]\s*[:\-–]?\s*([^.;]{2,80})", r"м[кк]?В|мкВ")
    grab("selectivity", r"(?:избирательност|селективност)\w*\s*[:\-–]?\s*([^.;]{2,60})", r"дБ")
    grab("output_power", r"(?:максимальная\s+)?выходная мощность\s*[:\-–]?\s*([^.;]{2,60})", r"м?Вт")
    # Только звуковой тракт: «диапазон (принимаемых) частот» — это диапазоны приёма в кГц/МГц
    grab(
        "frequency_response",
        r"(?:полоса|диапазон)\s+(?:(?:воспроизводимых|звуковых)\s+)?частот(?!\s+приём)"
        r"(?:\s+по\s+звуковому\s+давлению)?\s*[:\-–]?\s*(?:от\s+)?(\d[\d\s,.…\-–]*?(?:\s*до\s*)?\d+\s*[кКмМ]?Гц)",
        r"\d\s*Гц",
        reject=r"[кКмМ]Гц",
    )
    grab("power_supply", r"питание\s*[:\-–]?\s*([^.;]{2,80})", r"В|батаре|крона|кбс|элемент")
    grab("dimensions", r"(\d+\s*[xх×]\s*\d+(?:\s*[xх×]\s*\d+)?\s*мм)")
    grab("weight", r"масса\s*[:\-–]?\s*(\d+(?:[.,]\d+)?\s*(?:кг|г|гр)\b)")
    grab("original_price", r"цена(?:\s+набора)?\s*[:\-–]?\s*(\d[^.;]{0,40}руб[^.;]{0,20})")
    match = re.search(r"на\s+(\d+)\s+транзистор", text, re.I)
    if match:
        specs["transistor_count"] = int(match.group(1))
    match = re.search(
        r"с\s+((?:19|20)\d{2})\s*(?:года)?\s*(?:по|до)\s+((?:19|20)\d{2})",
        text,
        re.I,
    )
    if match:
        specs.setdefault("year_start", int(match.group(1)))
        specs.setdefault("year_end", int(match.group(2)))
    else:
        match = re.search(r"с\s+((?:19|20)\d{2})\s+года", text, re.I)
        if match:
            specs.setdefault("year_start", int(match.group(1)))
    return specs


def extract_bands(text: str) -> list[str]:
    codes = []
    for code in ("УКВ", "ДВ", "СВ", "КВ", "FM"):
        if re.search(rf"\b{code}\b", text, flags=re.I):
            codes.append("FM" if code == "FM" else code)
    return codes


def first_photo_url(html: str, page_url: str) -> str:
    for href in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.I):
        href = unescape(href).strip()
        if not re.search(r"\.(jpg|jpeg|png)$", href, re.I):
            continue
        if NAV_IMG.search(href):
            continue
        return urljoin(page_url, href)
    return ""


def enrich(rows: list[dict]) -> None:
    for i, row in enumerate(rows, 1):
        url = row["source_url"]
        try:
            html = decode(fetch(url))
        except Exception as exc:
            print(f"  skip {url}: {exc}", flush=True)
            continue
        description = extract_description(html)
        specs = extract_specs(description)
        if description:
            row["description"] = description
        if not row.get("year_start") and specs.get("year_start"):
            row["year_start"] = specs["year_start"]
            row["years"] = str(specs["year_start"])
        if not row.get("year_end") and specs.get("year_end"):
            row["year_end"] = specs["year_end"]
            if row.get("year_start") and row["year_end"] != row["year_start"]:
                row["years"] = f"{row['year_start']}–{row['year_end']}"
        for key in (
            "sensitivity",
            "selectivity",
            "output_power",
            "frequency_response",
            "power_supply",
            "dimensions",
            "weight",
            "original_price",
            "transistor_count",
        ):
            if key in specs:
                value = specs[key]
                if key in FIELD_LIMITS and isinstance(value, str):
                    value = clip(value, FIELD_LIMITS[key])
                row[key] = value
        bands = extract_bands(description)
        if bands:
            row["bands"] = bands
        photo = first_photo_url(html, url)
        if photo:
            row["photo_url"] = photo
        print(f"  [{i}/{len(rows)}] {row['name']}", flush=True)
        time.sleep(0.15)


def save_json(rows: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)
    slim = []
    for row in rows:
        slim.append(
            {
                "name": row["name"],
                "category": "konstr",
                "path": row["path"],
                "source_url": row["source_url"],
                "years": row.get("years", ""),
                "year_start": row.get("year_start"),
                "year_end": row.get("year_end"),
                "description": row.get("description", ""),
                "bands": row.get("bands", []),
                "sensitivity": row.get("sensitivity", ""),
                "selectivity": row.get("selectivity", ""),
                "output_power": row.get("output_power", ""),
                "frequency_response": row.get("frequency_response", ""),
                "power_supply": row.get("power_supply", ""),
                "dimensions": row.get("dimensions", ""),
                "weight": row.get("weight", ""),
                "original_price": row.get("original_price", ""),
                "transistor_count": row.get("transistor_count"),
                "photo_url": row.get("photo_url", ""),
            }
        )
    (DATA / "constructors.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    categories = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    if not any(cat["code"] == "konstr" for cat in categories):
        categories.append(
            {
                "code": "konstr",
                "name": "Радиоконструкторы",
                "short_name": "Радиоконструкторы",
                "slug": "radiokonstruktory",
                "sort_order": 16,
            }
        )
        (DATA / "categories.json").write_text(
            json.dumps(categories, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    catalog = json.loads((DATA / "all_catalog.json").read_text(encoding="utf-8"))
    catalog = [item for item in catalog if item.get("category") != "konstr"]
    catalog.extend(
        {
            "name": row["name"],
            "category": "konstr",
            "path": row["path"],
            "source_url": row["source_url"],
            "years": row.get("years", ""),
        }
        for row in slim
    )
    (DATA / "all_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def import_db(rows: list[dict]) -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radiotsekh.settings")
    import django

    django.setup()

    from django.core.files.base import ContentFile
    from slugify import slugify as slugify_ru

    from catalog.management.commands.seed_catalog import make_slug, match_factories, parse_years
    from catalog.models import Band, Factory, Receiver, ReceiverCategory

    category, _ = ReceiverCategory.objects.update_or_create(
        code="konstr",
        defaults={
            "name": "Радиоконструкторы",
            "short_name": "Радиоконструкторы",
            "slug": "radiokonstruktory",
            "sort_order": 16,
            "is_visible": True,
        },
    )
    factories = list(Factory.objects.all())
    keywords = {}
    raw_factories = json.loads((DATA / "factories.json").read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in raw_factories}
    for factory in factories:
        keywords[factory.pk] = [k.lower() for k in by_name.get(factory.name, {}).get("keywords", [])]
        if factory.short_name:
            keywords[factory.pk].append(factory.short_name.lower())
    bands = {band.code: band for band in Band.objects.all()}
    used = set(Receiver.objects.values_list("slug", flat=True))
    created = updated = 0
    for row in rows:
        receiver = (
            Receiver.objects.filter(category=category, source_url=row["source_url"]).first()
            or Receiver.objects.filter(category=category, name=row["name"]).first()
        )
        years = row.get("years") or ""
        start, end, prototype = parse_years(years)
        start = row.get("year_start") or start
        end = row.get("year_end") or end
        fields = {
            "name": row["name"],
            "category": category,
            "source_url": row.get("source_url", ""),
            "year_start": start,
            "year_end": end,
            "is_prototype": prototype,
            "description": row.get("description") or "",
            "sensitivity": clip(row.get("sensitivity") or "", FIELD_LIMITS["sensitivity"]),
            "selectivity": clip(row.get("selectivity") or "", FIELD_LIMITS["selectivity"]),
            "output_power": clip(row.get("output_power") or "", FIELD_LIMITS["output_power"]),
            "frequency_response": clip(row.get("frequency_response") or "", FIELD_LIMITS["frequency_response"]),
            "power_supply": clip(row.get("power_supply") or "", FIELD_LIMITS["power_supply"]),
            "dimensions": clip(row.get("dimensions") or "", FIELD_LIMITS["dimensions"]),
            "weight": clip(row.get("weight") or "", FIELD_LIMITS["weight"]),
            "original_price": clip(row.get("original_price") or "", FIELD_LIMITS["original_price"]),
            "transistor_count": row.get("transistor_count"),
        }
        if receiver:
            for key, value in fields.items():
                setattr(receiver, key, value)
            receiver.save()
            updated += 1
        else:
            receiver = Receiver.objects.create(
                slug=make_slug(row["name"], used),
                **fields,
            )
            created += 1
        if row.get("description"):
            receiver.factories.set(match_factories(row["description"], factories, keywords))
        if row.get("bands"):
            receiver.bands.set([bands[code] for code in row["bands"] if code in bands])
        photo_url = row.get("photo_url")
        if photo_url and not receiver.photo:
            try:
                raw = fetch(photo_url)
                ext = Path(urlparse(photo_url).path).suffix.lower() or ".jpg"
                if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                    ext = ".jpg"
                filename = f"{slugify_ru(receiver.slug)}{ext}"
                receiver.photo.save(filename, ContentFile(raw), save=True)
                time.sleep(0.1)
            except Exception as exc:
                print(f"  photo skip {receiver.name}: {exc}", flush=True)
    print(f"db created={created} updated={updated} total={category.receivers.count()}")


def main() -> None:
    from_json = "--from-json" in sys.argv
    if from_json and (DATA / "constructors.json").exists():
        rows = json.loads((DATA / "constructors.json").read_text(encoding="utf-8"))
        print(f"from json: {len(rows)}")
    else:
        if not INDEX_FILE.exists():
            INDEX_FILE.write_bytes(fetch(INDEX_URL))
        html = decode(INDEX_FILE.read_bytes())
        rows = parse_index(html)
        print(f"index models: {len(rows)}")
        enrich(rows)
        save_json(rows)
    import_db(rows)
    for row in rows:
        print(f"  {row.get('year_start') or '----'}  {row['name']}")


if __name__ == "__main__":
    main()
