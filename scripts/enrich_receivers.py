#!/usr/bin/env python3
"""Fill empty receiver cards from rw6ase source pages."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROGRESS = DATA / "enrich_progress.json"
sys.path.insert(0, str(ROOT))

from scripts.import_constructors import (  # noqa: E402
    FIELD_LIMITS,
    USER_AGENT,
    clip,
    decode,
    extract_bands,
    extract_description,
    extract_specs,
    fetch,
    first_photo_url,
)

YEAR_RE = re.compile(
    r"с\s+(?:[IVX]+-?\s*кв\.?\s+|(?:января|февраля|марта|апреля|мая|июня|"
    r"июля|августа|сентября|октября|ноября|декабря)\s+)?((?:19|20)\d{2})\s+года",
    re.I,
)
END_YEAR_RE = re.compile(
    r"с\s+(?:[IVX]+-?\s*кв\.?\s+)?((?:19|20)\d{2})\s*(?:года)?\s*(?:по|до)\s+((?:19|20)\d{2})",
    re.I,
)


def load_progress() -> set[int]:
    if not PROGRESS.exists():
        return set()
    raw = json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {int(x) for x in raw}


def save_progress(done: set[int]) -> None:
    PROGRESS.write_text(json.dumps(sorted(done)), encoding="utf-8")


def needs_enrich(receiver) -> bool:
    if not receiver.source_url:
        return False
    if not receiver.description or not receiver.photo or not receiver.year_start:
        return True
    return False


def years_from_text(text: str) -> tuple[int | None, int | None, str]:
    match = END_YEAR_RE.search(text)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        if end != start:
            return start, end, f"{start}–{end}"
        return start, None, str(start)
    match = YEAR_RE.search(text)
    if match:
        start = int(match.group(1))
        return start, None, str(start)
    return None, None, ""


def apply_row(receiver, payload: dict, factories, keywords, bands) -> list[str]:
    from catalog.management.commands.seed_catalog import match_factories

    changed: list[str] = []

    def fill(field: str, value) -> None:
        if value in (None, ""):
            return
        current = getattr(receiver, field)
        if current in (None, ""):
            setattr(receiver, field, value)
            changed.append(field)

    fill("description", payload.get("description"))
    start = payload.get("year_start")
    end = payload.get("year_end")
    fill("year_start", start)
    fill("year_end", end)
    for key in FIELD_LIMITS:
        value = payload.get(key)
        if isinstance(value, str):
            value = clip(value, FIELD_LIMITS[key])
        fill(key, value)
    fill("transistor_count", payload.get("transistor_count"))
    if changed:
        receiver.save(update_fields=changed)

    if payload.get("description") and not receiver.factories.exists():
        found = match_factories(payload["description"], factories, keywords)
        if found:
            receiver.factories.set(found)
            changed.append("factories")
    if payload.get("bands") and not receiver.bands.exists():
        receiver.bands.set([bands[code] for code in payload["bands"] if code in bands])
        changed.append("bands")
    return changed


def download_photo(receiver, photo_url: str) -> bool:
    from django.core.files.base import ContentFile
    from slugify import slugify as slugify_ru

    if receiver.photo or not photo_url:
        return False
    try:
        raw = fetch(photo_url)
    except Exception as exc:
        print(f"  photo skip {receiver.name}: {exc}", flush=True)
        return False
    if len(raw) < 1500:
        return False
    ext = Path(urlparse(photo_url).path).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    filename = f"{slugify_ru(receiver.slug)}{ext}"
    receiver.photo.save(filename, ContentFile(raw), save=True)
    return True


def parse_page(url: str) -> dict:
    html = decode(fetch(url))
    description = extract_description(html)
    specs = extract_specs(description)
    start, end, years = years_from_text(description)
    if not start and specs.get("year_start"):
        start = specs["year_start"]
        years = years or str(start)
    if not end and specs.get("year_end"):
        end = specs["year_end"]
        if start and end and end != start:
            years = f"{start}–{end}"
    payload = {
        "description": description,
        "year_start": start,
        "year_end": end,
        "years": years,
        "bands": extract_bands(description),
        "photo_url": first_photo_url(html, url),
    }
    for key, value in specs.items():
        if key not in payload:
            payload[key] = value
    return payload


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radiotsekh.settings")
    import django

    django.setup()

    from catalog.management.commands.seed_catalog import match_factories  # noqa: F401
    from catalog.models import Band, Factory, Receiver

    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    factories = list(Factory.objects.all())
    raw_factories = json.loads((DATA / "factories.json").read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in raw_factories}
    keywords = {}
    for factory in factories:
        keywords[factory.pk] = [k.lower() for k in by_name.get(factory.name, {}).get("keywords", [])]
        if factory.short_name:
            keywords[factory.pk].append(factory.short_name.lower())
    bands = {band.code: band for band in Band.objects.all()}

    done = load_progress()
    qs = (
        Receiver.objects.exclude(source_url="")
        .select_related("category")
        .prefetch_related("factories", "bands")
        .order_by("category__sort_order", "name")
    )
    todo = [r for r in qs if r.pk not in done and needs_enrich(r)]
    if limit:
        todo = todo[:limit]
    print(f"to enrich: {len(todo)} (already {len(done)})", flush=True)

    ok = fail = 0
    for i, receiver in enumerate(todo, 1):
        try:
            payload = parse_page(receiver.source_url)
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{len(todo)}] FAIL {receiver.name}: {exc}", flush=True)
            done.add(receiver.pk)
            if i % 20 == 0:
                save_progress(done)
            time.sleep(0.2)
            continue
        changed = apply_row(receiver, payload, factories, keywords, bands)
        photo = download_photo(receiver, payload.get("photo_url", ""))
        if photo:
            changed.append("photo")
        ok += 1
        done.add(receiver.pk)
        print(
            f"  [{i}/{len(todo)}] {receiver.category.code if receiver.category else '-'} "
            f"{receiver.name}: {', '.join(changed) or 'nothing'}",
            flush=True,
        )
        if i % 20 == 0:
            save_progress(done)
        time.sleep(0.12)

    save_progress(done)
    print(f"done ok={ok} fail={fail} saved={len(done)}")


if __name__ == "__main__":
    main()
