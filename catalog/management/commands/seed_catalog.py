import json
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from slugify import slugify as slugify_ru

from django.contrib.auth.models import Group

from catalog.models import Band, Factory, Receiver, ReceiverCategory
from catalog.permissions import SELLER_GROUP

DATA = settings.BASE_DIR / "data"

BANDS = [
    ("ДВ", "Длинные волны"),
    ("СВ", "Средние волны"),
    ("КВ", "Короткие волны"),
    ("УКВ", "Ультракороткие волны (ЧМ)"),
    ("FM", "FM (87,5–108 МГц)"),
]

FEATURED_SPECS = {
    "Альпинист": {
        "description": (
            "Переносной радиоприёмник «Альпинист» выпускали с 1964 года Воронежский и "
            "Грозненский радиозаводы. Это первая модель линейки: разработка начата в 1963 году "
            "на базе «Атмосферы-2М». Приёмник рассчитан на ДВ и СВ, питание — две батареи КБС-Л-0,5."
        ),
        "sensitivity": "ДВ 2,5 мВ/м, СВ 1,5 мВ/м",
        "selectivity": "по соседнему и зеркальному каналам 26…30 дБ",
        "output_power": "номинальная 150 мВт, максимальная 270 мВт",
        "frequency_response": "300…3500 Гц",
        "power_supply": "2 × КБС-Л-0,5",
        "dimensions": "215 × 145 × 60 мм",
        "weight": "1,5 кг с батареями",
        "is_featured": True,
    },
    "ВЭФ-Спидола": {
        "description": (
            "Портативный транзисторный радиоприёмник «ВЭФ-Спидола» (ПМК-65) с 1965 года "
            "выпускал Рижский государственный электротехнический завод ВЭФ. Работает на ДВ, СВ "
            "и пяти поддиапазонах КВ. Экспортный вариант назывался Convair-1 и имел шесть КВ-поддиапазонов."
        ),
        "dimensions": "275 × 200 × 92 мм",
        "weight": "2,3 кг",
        "original_price": "75 руб. 82 коп.",
        "is_featured": True,
    },
    "Спидола": {
        "description": (
            "ПМП-60 — один из первых массовых портативных полупроводниковых приёмников СССР. "
            "С I квартала 1960 года выпускался на ВЭФ и задал линейку всеволновых рижских моделей."
        ),
        "is_featured": True,
        "receiver_class": "2",
    },
    "Сокол": {
        "description": (
            "Самая массовая модель Московского радиозавода: супергетеродин 4-го класса на 7 транзисторах, "
            "диапазоны ДВ и СВ. Выпускался с 1963 по 1971 год и стал основой линейки «Сокол-2», «Сокол-4»."
        ),
        "transistor_count": 7,
        "receiver_class": "4",
        "is_featured": True,
    },
    "Океан-209": {
        "description": (
            "Всеволновый портативный приёмник Минского ПТО «Горизонт»: ДВ, СВ, пять КВ-поддиапазонов и УКВ. "
            "Одна из самых узнаваемых моделей 1970-х, удобная для модернизации УНЧ и УКВ-тракта."
        ),
        "is_featured": True,
    },
    "ВЭФ-202": {
        "description": (
            "Наследник «ВЭФ-201»: ДВ, СВ и пять КВ-поддиапазонов. С I квартала 1971 года — одна из "
            "самых ремонтопригодных рижских схем, для которой существуют современные платы УНЧ и преобразователя."
        ),
        "is_featured": True,
    },
    "Нейва": {
        "description": (
            "Супергетеродин Каменск-Уральского приборостроительного завода на 7 транзисторах. "
            "Схема общая с опытным «Сигналом» и днепропетровским «Юпитером»; серия с 1965 года."
        ),
        "transistor_count": 7,
        "is_featured": True,
    },
    "Меридиан-202": {
        "description": (
            "Киевский всеволновый приёмник 1973 года: ДВ, СВ, КВ и УКВ. Удобный кандидат на замену "
            "УКВ-блока и перевод выходного каскада на современную элементную базу."
        ),
        "is_featured": True,
    },
    "Океан / Океан-201": {"is_featured": True},
    "Селга": {"is_featured": True},
}


def norm(value: str) -> str:
    value = (value or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", value).strip()


def name_keys(name: str) -> set[str]:
    compact = re.sub(r"[^a-zа-я0-9]+", "", norm(name))
    keys = {compact, re.sub(r"(рп|rp)", "", compact)}
    for part in re.split(r"[/,]", name):
        part_c = re.sub(r"[^a-zа-я0-9]+", "", norm(part))
        if part_c:
            keys.add(part_c)
            keys.add(re.sub(r"(рп|rp)", "", part_c))
    return {k for k in keys if k}


def parse_years(years: str) -> tuple[int | None, int | None, bool]:
    nums = [int(x) for x in re.findall(r"(?:19|20)\d{2}", years or "")]
    prototype = "опытн" in (years or "").lower() or "разработ" in (years or "").lower()
    start = nums[0] if nums else None
    end = nums[1] if len(nums) > 1 else None
    return start, end, prototype


def parse_bands(bands_text: str) -> tuple[list[str], str]:
    codes = []
    for code in ("УКВ", "ДВ", "СВ", "КВ", "FM"):
        if re.search(rf"\b{code}\b", bands_text or "", flags=re.I):
            codes.append("FM" if code == "FM" else code)
    note = ""
    extra = re.search(r"\(([^)]+)\)", bands_text or "")
    if extra:
        note = extra.group(1)
    return codes, note


def make_slug(text: str, used: set[str]) -> str:
    slug = slugify_ru(text) or slugify(text) or "model"
    base = slug
    i = 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


def match_factories(text: str, factories: list[Factory], keywords: dict[int, list[str]]) -> list[Factory]:
    hay = norm(text)
    found = []
    for factory in factories:
        for keyword in sorted(keywords[factory.pk], key=len, reverse=True):
            if keyword and keyword in hay:
                found.append(factory)
                break
    if "вэф" in hay and "радиотехник" not in hay:
        found = [f for f in found if "радиотехник" not in f.name.lower()]
    return found


class Command(BaseCommand):
    help = "Заполняет библиотеку заводами, диапазонами, категориями и приёмниками"

    def handle(self, *args, **options):
        factories = self._seed_factories()
        bands = self._seed_bands()
        categories = self._seed_categories()
        used_slugs: set[str] = set(Receiver.objects.values_list("slug", flat=True))
        receivers = self._seed_pdf_receivers(factories, bands, used_slugs)
        self._seed_catalog_index(receivers, used_slugs, categories)
        self._apply_featured()
        Group.objects.get_or_create(name=SELLER_GROUP)
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: {Factory.objects.count()} заводов, "
                f"{Receiver.objects.count()} приёмников"
            )
        )

    def _seed_factories(self):
        raw = json.loads((DATA / "factories.json").read_text(encoding="utf-8"))
        keywords = {}
        factories = []
        used = set()
        for item in raw:
            slug = make_slug(item["short_name"] or item["name"], used)
            republic = item.get("republic") or ""
            region = item.get("region") or ""
            if not region:
                for ssr, _label in Factory.Republic.choices:
                    if ssr and ssr in republic:
                        region = republic.replace(ssr, "").strip(" ,")
                        republic = ssr
                        break
            factory, _ = Factory.objects.update_or_create(
                name=item["name"],
                defaults={
                    "short_name": item["short_name"],
                    "slug": slug,
                    "city_then": item["city_then"],
                    "republic": republic,
                    "region": region,
                    "country_now": item["country_now"],
                    "city_now": item["city_now"],
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "kind": item["kind"],
                    "description": (
                        f"{item['name']} — {item['city_then']}, {item['republic']}. "
                        f"Сейчас: {item['city_now']}, {item['country_now']}."
                    ),
                },
            )
            keywords[factory.pk] = [norm(k) for k in item.get("keywords", [])]
            factories.append(factory)
        self.factory_keywords = keywords
        return factories

    def _seed_bands(self):
        result = {}
        for code, name in BANDS:
            band, _ = Band.objects.update_or_create(code=code, defaults={"name": name})
            result[code] = band
        return result

    def _seed_categories(self):
        rows = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
        result = {}
        for row in rows:
            category, _ = ReceiverCategory.objects.update_or_create(
                code=row["code"],
                defaults={
                    "name": row["name"],
                    "short_name": row["short_name"],
                    "slug": row["slug"],
                    "sort_order": row["sort_order"],
                },
            )
            result[row["code"]] = category
        return result

    def _seed_pdf_receivers(self, factories, bands, used_slugs):
        rows = json.loads((DATA / "receivers.json").read_text(encoding="utf-8"))
        created = {}
        for row in rows:
            name = re.sub(r"\s+", " ", row["name"]).strip()
            years = row["years"]
            start, end, prototype = parse_years(years)
            slug_source = name if Receiver.objects.filter(name=name).count() <= 1 else f"{name}-{start or years}"
            existing = Receiver.objects.filter(name=name, year_start=start).first()
            if existing:
                receiver = existing
            else:
                slug = make_slug(slug_source, used_slugs)
                receiver = Receiver(name=name, slug=slug)
            receiver.year_start = start
            receiver.year_end = end
            receiver.is_prototype = prototype
            receiver.notes = row.get("note") or receiver.notes
            if not receiver.description and row.get("note"):
                receiver.description = row["note"]
            receiver.save()
            receiver.factories.set(match_factories(row["factory"], factories, self.factory_keywords))
            codes, note = parse_bands(row["bands"])
            receiver.bands.set([bands[c] for c in codes if c in bands])
            if note:
                receiver.bands_note = note
                receiver.save(update_fields=["bands_note"])
            created.setdefault(name, receiver)
            for key in name_keys(name):
                created[key] = receiver
        return created

    def _seed_catalog_index(self, receivers, used_slugs, categories):
        index = json.loads((DATA / "all_catalog.json").read_text(encoding="utf-8"))
        portable = categories.get("pp")
        for item in index:
            name = item["name"]
            category = categories.get(item.get("category", "pp"))
            keys = name_keys(name)
            source_url = item.get("source_url", "")
            # Одна страница источника = одна модель. Источник публикует некоторые модели
            # в двух разделах (например, «Ламповые» и «Радиолы») — категорию не перебиваем.
            match = Receiver.objects.filter(source_url=source_url).first() if source_url else None
            if match:
                category = match.category or category
            elif category:
                # Разные модели с одинаковым названием («Ленинград» 1957 и транзисторный)
                # различаются источником; по имени сопоставляем только записи без источника.
                match = Receiver.objects.filter(name=name, category=category, source_url="").first()
            if not match and category == portable:
                for key in keys:
                    if key in receivers and not receivers[key].source_url:
                        match = receivers[key]
                        break
                if not match:
                    match = Receiver.objects.filter(name=name, category__isnull=True, source_url="").first()
                if not match:
                    match = Receiver.objects.filter(name=name, category=portable, source_url="").first()
            extras = {}
            if item.get("years") and (not match or not match.year_start):
                start, end, prototype = parse_years(item["years"])
                extras["year_start"] = start
                extras["year_end"] = end
                extras["is_prototype"] = prototype
            if item.get("description") and (not match or not match.description):
                extras["description"] = item["description"]
            if match:
                updates = []
                if category and match.category_id != category.pk:
                    match.category = category
                    updates.append("category")
                if item.get("source_url") and not match.source_url:
                    match.source_url = item["source_url"]
                    updates.append("source_url")
                for field, value in extras.items():
                    setattr(match, field, value)
                    updates.append(field)
                if updates:
                    match.save(update_fields=updates)
                continue
            receiver = Receiver.objects.create(
                name=name,
                slug=make_slug(name, used_slugs),
                category=category,
                source_url=item.get("source_url", ""),
                **extras,
            )
            if category == portable:
                for key in keys:
                    receivers[key] = receiver
        if portable:
            Receiver.objects.filter(category__isnull=True).update(category=portable)

    def _apply_featured(self):
        for name, extras in FEATURED_SPECS.items():
            receiver = Receiver.objects.filter(name=name).first()
            if not receiver:
                continue
            for field, value in extras.items():
                setattr(receiver, field, value)
            receiver.save()
