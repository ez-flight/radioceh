#!/usr/bin/env python3
"""Parse rw6ase factory list (PDF) and import plants that made radio gear."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PDF_PATH = DATA / "zd_v9.6.pdf"
PDF_URL = "https://rw6ase.narod.ru/index0/zd_v9.6.pdf"
JSON_PATH = DATA / "rw6ase_factories.json"
USER_AGENT = "Mozilla/5.0 (compatible; RadiotsekhCatalog/1.0)"

HISTORY_START = re.compile(
    r"^(Основан|Образован|Входил|Создан|Преобразован|Перепрофилирован|Реорганизован)\b"
)
PRODUCT_START = re.compile(
    r"^(?:рп|тл|мг|мл|аг|ус|пт|ант|пкд|цм|ап|тф|мк|вк|рд|эм|тв|тм|тб|дв|рл|"
    r"мп|уп|бп|ак|гг|ас|эф|фм|сд|ик|кв|св)\b",
    re.I,
)
POSTAL = re.compile(r"^\d{5,6}\b")
CITY_RE = re.compile(
    r"г\.\s*("
    r"Великие\s+Луки|Великий\s+Новгород|Ростов-на[-\s]Дону|Павловский\s+Посад|"
    r"Нижний\s+Новгород|Сергиев\s+Посад|Комсомольск-на-Амуре|Каменск-Уральский|"
    r"Новая\s+Каховка|Усть-Джегута|Майлуу-Суу|Малая\s+Вишера|Красный\s+Луч|"
    r"Старая\s+Майна|"
    r"[А-ЯЁ][А-Яа-яё\-]+"
    r")"
)
CITY_LOOSE = re.compile(r"\bг[.,]?\s+([А-ЯЁ][А-Яа-яё\-]+)")
NAME_CITY = {
    "ленинградский": "Ленинград",
    "московский": "Москва",
    "киевский": "Киев",
    "минский": "Минск",
    "харьковский": "Харьков",
    "саратовский": "Саратов",
    "сарапульский": "Сарапул",
    "челябинский": "Челябинск",
    "черкесский": "Черкесск",
    "новосибирский": "Новосибирск",
    "воронежский": "Воронеж",
    "горьковский": "Горький",
    "казанский": "Казань",
    "ижевский": "Ижевск",
    "уфимский": "Уфа",
    "одесский": "Одесса",
    "рижский": "Рига",
    "львовский": "Львов",
    "днепропетровский": "Днепропетровск",
    "запорожский": "Запорожье",
    "ереванский": "Ереван",
    "бакинский": "Баку",
    "бердский": "Бердск",
    "грозненский": "Грозный",
    "муромский": "Муром",
    "пензенский": "Пенза",
    "томский": "Томск",
    "тульский": "Тула",
    "ярославский": "Ярославль",
    "нальчикский": "Нальчик",
    "ульяновский": "Ульяновск",
    "костромской": "Кострома",
    "касимовский": "Касимов",
    "бережанский": "Бережаны",
    "дербентский": "Дербент",
    "севастопольский": "Севастополь",
    "учкекенский": "Учкекен",
}
QUOTED_RE = re.compile(r"[«\"]([^»\"]{2,40})[»\"]")
NAME_OK = re.compile(
    r"завод|фабрик|радиозавод|мотозавод|НИИ|ВНИИ|СКБ|ЦКБ|\bКБ\b|НПО|ЗАО|комбинат|трест",
    re.I,
)

CITY_NOW = {
    "Ленинград": "Санкт-Петербург",
    "Горький": "Нижний Новгород",
    "Свердловск": "Екатеринбург",
    "Куйбышев": "Самара",
    "Калинин": "Тверь",
    "Ворошиловград": "Луганск",
    "Днепропетровск": "Днепр",
    "Алма-Ата": "Алматы",
    "Фрунзе": "Бишкек",
    "Кишинев": "Кишинёв",
    "Кишинёв": "Кишинёв",
    "Целиноград": "Астана",
    "Сталинабад": "Душанбе",
    "Куйбышевск": "Самара",
    "Загорск": "Сергиев Посад",
    "Новгород": "Великий Новгород",
    "Устинов": "Ижевск",
    "Горький": "Нижний Новгород",
    "Вильнюс": "Вильнюс",
    "Бельцы": "Бельцы",
    "Каунас": "Каунас",
}

COUNTRY_HINTS = [
    ("Армения", "Армения", "Армянская ССР"),
    ("Азербайджан", "Азербайджан", "Азербайджанская ССР"),
    ("Беларусь", "Беларусь", "Белорусская ССР"),
    ("Белоруссия", "Беларусь", "Белорусская ССР"),
    ("Казахстан", "Казахстан", "Казахская ССР"),
    ("Кыргызстан", "Кыргызстан", "Киргизская ССР"),
    ("Киргиз", "Кыргызстан", "Киргизская ССР"),
    ("Латвия", "Латвия", "Латвийская ССР"),
    ("Литва", "Литва", "Литовская ССР"),
    ("Молдов", "Молдова", "Молдавская ССР"),
    ("Таджикистан", "Таджикистан", "Таджикская ССР"),
    ("Туркмен", "Туркменистан", "Туркменская ССР"),
    ("Узбекистан", "Узбекистан", "Узбекская ССР"),
    ("Украина", "Украина", "Украинская ССР"),
    ("Эстония", "Эстония", "Эстонская ССР"),
    ("Грузия", "Грузия", "Грузинская ССР"),
]

CITY_COORDS = {
    "Абовян": (40.2739, 44.6256),
    "Алагир": (43.0417, 44.2222),
    "Александров": (56.3977, 38.7276),
    "Альметьевск": (54.9014, 52.2973),
    "Алма-Ата": (43.2364, 76.9457),
    "Алматы": (43.2364, 76.9457),
    "Барнаул": (53.3461, 83.7766),
    "Арзамас": (55.3948, 43.8407),
    "Баку": (40.3756, 49.8328),
    "Белгород": (50.5954, 36.5873),
    "Белово": (54.4224, 86.3036),
    "Бельцы": (47.7617, 27.9289),
    "Бердск": (54.758, 83.1068),
    "Бережаны": (49.4461, 24.9374),
    "Богородицк": (53.7717, 38.1222),
    "Брест": (52.0975, 23.6877),
    "Брянск": (53.2434, 34.364),
    "Великий Березный": (48.8922, 22.4556),
    "Великие Луки": (56.34, 30.5452),
    "Вильнюс": (54.6872, 25.2797),
    "Винница": (49.2331, 28.4682),
    "Витебск": (55.1904, 30.2049),
    "Владивосток": (43.1151, 131.8856),
    "Владикавказ": (43.0246, 44.6819),
    "Владимир": (56.1296, 40.4066),
    "Волжский": (48.7978, 44.7461),
    "Вологда": (59.2205, 39.8915),
    "Воронеж": (51.6606, 39.2006),
    "Гомель": (52.4345, 30.9754),
    "Городня": (51.8906, 31.5944),
    "Горький": (56.2965, 43.9361),
    "Гродно": (53.6694, 23.8131),
    "Грозный": (43.3086, 45.7066),
    "Дербент": (42.0678, 48.2899),
    "Джалал-Абад": (40.9333, 73.0),
    "Днепр": (48.4647, 35.0462),
    "Днепропетровск": (48.4647, 35.0462),
    "Донецк": (48.0159, 37.8028),
    "Душанбе": (38.5598, 68.774),
    "Артемовский": (57.3722, 61.8778),
    "Ереван": (40.1792, 44.4991),
    "Жигулевск": (53.4011, 49.4947),
    "Сергиев Посад": (56.3155, 38.135),
    "Загорск": (56.3155, 38.135),
    "Запорожье": (47.8388, 35.1396),
    "Зеленоград": (55.9825, 37.1814),
    "Ижевск": (56.8527, 53.2115),
    "Иркутск": (52.2864, 104.2807),
    "Казань": (55.7887, 49.1221),
    "Калуга": (54.5138, 36.2612),
    "Каменец-Подольский": (48.6845, 26.585),
    "Каменск-Уральский": (56.4155, 61.9178),
    "Кандава": (57.0375, 22.7771),
    "Канев": (49.75, 31.47),
    "Карпинск": (59.7667, 60.0),
    "Касимов": (54.9411, 41.3953),
    "Киев": (50.45, 30.5241),
    "Кимовск": (53.9711, 38.5311),
    "Кировоград": (48.5079, 32.2623),
    "Кропивницкий": (48.5079, 32.2623),
    "Киров": (58.6036, 49.668),
    "Кишинёв": (47.0105, 28.8638),
    "Кишинев": (47.0105, 28.8638),
    "Комсомольск-на-Амуре": (50.5496, 137.0078),
    "Красный Луч": (48.1397, 38.9372),
    "Красносельск": (53.6, 24.15),
    "Красноярск": (56.0153, 92.8932),
    "Кузнецк": (53.1168, 46.6004),
    "Куйбышев": (53.1959, 50.1002),
    "Самара": (53.1959, 50.1002),
    "Кулебаки": (55.4133, 42.5325),
    "Курган": (55.4444, 65.3161),
    "Курск": (51.7304, 36.1926),
    "Кыштым": (55.7085, 60.5415),
    "Ленинград": (59.9343, 30.3351),
    "Санкт-Петербург": (59.9343, 30.3351),
    "Лермонтов": (44.1061, 42.9731),
    "Лобня": (56.0126, 37.4744),
    "Львов": (49.8397, 24.0297),
    "Йошкар-Ола": (56.6372, 47.8919),
    "Маркс": (51.7111, 46.7486),
    "Махачкала": (42.9849, 47.5047),
    "Миасс": (55.045, 60.1078),
    "Минск": (53.9025, 27.5618),
    "Могилев": (53.9007, 30.3314),
    "Молодечно": (54.3136, 26.8453),
    "Москва": (55.7558, 37.6173),
    "Муром": (55.575, 42.0426),
    "Нальчик": (43.4853, 43.6071),
    "Николаев": (46.975, 31.9946),
    "Новгород": (58.521, 31.2758),
    "Великий Новгород": (58.521, 31.2758),
    "Новая Каховка": (46.7544, 33.3558),
    "Новолукомль": (54.6556, 29.15),
    "Новополоцк": (55.5318, 28.5987),
    "Новосибирск": (55.0084, 82.9357),
    "Обнинск": (55.0968, 36.6101),
    "Одесса": (46.4825, 30.7233),
    "Омск": (54.9885, 73.3242),
    "Оренбург": (51.7682, 55.097),
    "Орша": (54.5081, 30.4258),
    "Павловский Посад": (55.7819, 38.6503),
    "Пенза": (53.195, 45.0183),
    "Пермь": (58.0105, 56.2502),
    "Петровск": (52.3094, 45.3917),
    "Петропавловск": (54.8732, 69.15),
    "Подольск": (55.4312, 37.5447),
    "Полтава": (49.5883, 34.5514),
    "Порхов": (57.7667, 29.5567),
    "Ивано-Франковск": (48.9226, 24.7111),
    "Псков": (57.8194, 28.3318),
    "Раменское": (55.5669, 38.2303),
    "Рахов": (48.0586, 24.2006),
    "Рига": (56.9496, 24.1052),
    "Ровно": (50.6199, 26.2516),
    "Ростов-на-Дону": (47.2357, 39.7015),
    "Рыбинск": (58.0446, 38.8426),
    "Рязань": (54.6269, 39.6916),
    "Самарканд": (39.6542, 66.9597),
    "Саранск": (54.1874, 45.1839),
    "Сарапул": (56.4774, 53.8195),
    "Саратов": (51.5336, 46.0342),
    "Свердловск": (56.8389, 60.6057),
    "Екатеринбург": (56.8389, 60.6057),
    "Светловодск": (49.0454, 33.2072),
    "Светлоград": (45.3306, 42.8569),
    "Севастополь": (44.6166, 33.5254),
    "Симферополь": (44.9521, 34.1024),
    "Славгород": (52.9973, 78.647),
    "Смела": (49.2372, 31.8731),
    "Смоленск": (54.7826, 32.0453),
    "Ставрополь": (45.0445, 41.969),
    "Таганрог": (47.2362, 38.8969),
    "Тамбов": (52.7212, 41.4523),
    "Ташкент": (41.2995, 69.2401),
    "Томск": (56.4846, 84.9476),
    "Торжок": (57.0436, 34.9622),
    "Кызыл": (51.7191, 94.4378),
    "Тула": (54.1931, 37.6173),
    "Ужгород": (48.6208, 22.2879),
    "Улан-Удэ": (51.8335, 107.5841),
    "Ульяновск": (54.3142, 48.4031),
    "Умань": (48.7484, 30.2218),
    "Уфа": (54.7388, 55.9721),
    "Учкекен": (43.9333, 42.5167),
    "Фрунзе": (42.8746, 74.5698),
    "Бишкек": (42.8746, 74.5698),
    "Фрязино": (55.9606, 38.0456),
    "Харьков": (49.9935, 36.2304),
    "Херсон": (46.6354, 32.6169),
    "Хмельницкий": (49.4229, 26.9871),
    "Чайковский": (56.7667, 54.1167),
    "Челябинск": (55.1644, 61.4368),
    "Черкассы": (49.4444, 32.0598),
    "Чернигов": (51.4982, 31.2893),
    "Черновцы": (48.2917, 25.9352),
    "Черкесск": (44.2285, 42.0483),
    "Шадринск": (56.0852, 63.6335),
    "Михайловск": (45.1308, 42.0275),
    "Ярославль": (57.6261, 39.8845),
    "Элиста": (46.3078, 44.2558),
    "Канибадам": (40.2833, 70.4333),
    "Малая Вишера": (58.8456, 32.2247),
    "Старая Майна": (54.6083, 48.9306),
    "Бельц": (47.7617, 27.9289),
    "Барань": (54.4806, 30.3158),
    "Бельцы": (47.7617, 27.9289),
    "Боярка": (50.3292, 30.2886),
    "Волгоград": (48.708, 44.5133),
    "Волжск": (55.8664, 48.3561),
    "Гавар": (40.3539, 45.1239),
    "Гюмри": (40.7894, 43.8475),
    "Кировск": (67.6145, 33.6714),
    "Клинцы": (52.7566, 32.2393),
    "Кострома": (57.7677, 40.9269),
    "Лесной": (58.6333, 59.7833),
    "Люберцы": (55.6774, 37.8932),
    "Майлуу-Суу": (41.2453, 72.4486),
    "Макеевка": (48.0478, 37.9258),
    "Нововоронеж": (51.3103, 39.2189),
    "Уссурийск": (43.7973, 131.9517),
    "Ижевск": (56.8527, 53.2115),
    "Устинов": (56.8527, 53.2115),
    "Усть-Джегута": (44.1611, 41.9764),
    "Хабаровск": (48.4827, 135.0838),
    "Шяуляй": (55.9349, 23.3137),
    "Великие Луки": (56.34, 30.5452),
    "Нижний Новгород": (56.2965, 43.9361),
    "Ростов-на-Дону": (47.2357, 39.7015),
    "Павловский Посад": (55.7819, 38.6503),
    "Сергиев Посад": (56.3155, 38.135),
    "Комсомольск-на-Амуре": (50.5496, 137.0078),
    "Новая Каховка": (46.7544, 33.3558),
    "Каменск-Уральский": (56.4155, 61.9178),
}

ALIASES = {
    "рижский государственный электротехнический завод «вэф»": "Рижский государственный электротехнический завод ВЭФ",
    "рижский радиозавод им. попова": "Рижский радиозавод им. А. С. Попова («Радиотехника»)",
    "минский радиозавод": "Минский радиозавод / ПО «Горизонт»",
    "сарапульский завод им. орджоникидзе": "Сарапульский радиозавод им. Орджоникидзе",
    "ленинградский ниирпа им. а.с.попова": "Ленинградский НИИРПА им. А. С. Попова",
    "ленинградский механический завод «ленинец»": "Ленинградский механический завод «Ленинец»",
    "новгородский завод нпо «старт»": "Новгородский завод НПО «Старт»",
    "московский радиозавод": "Московский радиозавод / ПО «Темп»",
    "московский государственный радиозавод «красный октябрь»": "Московский завод «Красный Октябрь»",
    "челябинский радиозавод": "Челябинский радиозавод «Полёт»",
}


def fetch(url: str) -> bytes:
    from urllib.request import Request, urlopen

    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read()


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages).replace("\xa0", " ")


BAD_NAME_START = re.compile(
    r"^(Основа|Построен|Создан|Выделил|Государственн|С \d|В \d|НКЭП|НКБ|НПО |"
    r"п/я|Приборостроительный завод,|Октябрь|Ленина,|АО «|с \d|с середины|"
    r"с конца|Завод при|Завод «|ОАО |АООТ |ООО |РУП |ФГУП )"
)


def is_name(line: str) -> bool:
    line = line.strip()
    if len(line) < 8 or len(line) > 90:
        return False
    if not re.match(r"^[А-ЯЁ][а-яё]", line):
        return False
    if PRODUCT_START.match(line) or POSTAL.match(line) or HISTORY_START.match(line):
        return False
    if BAD_NAME_START.match(line) or line.startswith("Завод "):
        return False
    if re.match(r"^(Электромеханический|Приборостроительный|Машиностроительный) завод", line):
        return False
    if not NAME_OK.search(line):
        return False
    return bool(
        re.search(
            r"^[А-ЯЁ][а-яё\-]+(?:ский|цкий|нский|ский|ой|ая|ое|ий|инский)\s",
            line,
        )
        or re.search(r"радиозавод|НИИ|ВНИИ|СКБ|\bКБ\b|НПО", line)
    )


def parse_blocks(text: str) -> list[dict]:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    starts: list[int] = []
    for i, line in enumerate(lines):
        nxt = next((x for x in lines[i + 1 : i + 4] if x), "")
        same = HISTORY_START.search(line)
        if is_name(line) and (
            HISTORY_START.match(nxt)
            or POSTAL.match(nxt)
            or (nxt.startswith(line.split(",")[0][:20]) and "ОАО" in nxt)
            or same
        ):
            starts.append(i)
    starts.append(len(lines))
    rows = []
    seen = set()
    for a, b in zip(starts, starts[1:]):
        name = lines[a]
        name = re.sub(r"\s+" + HISTORY_START.pattern[1:], "", name).strip(" ,;")
        if name in seen or not is_name(name):
            continue
        seen.add(name)
        body = [ln for ln in lines[a + 1 : b] if ln]
        history_parts, address_parts, products = [], [], []
        for ln in body:
            if PRODUCT_START.match(ln):
                products.append(ln)
            elif POSTAL.match(ln) or (CITY_RE.search(ln) and not HISTORY_START.match(ln) and "Основан" not in ln):
                address_parts.append(ln)
            elif HISTORY_START.match(ln) or history_parts:
                if PRODUCT_START.match(ln) or POSTAL.match(ln):
                    continue
                history_parts.append(ln)
        address = " ".join(address_parts)
        history = " ".join(history_parts)
        city = ""
        cities = [c for c in CITY_RE.findall(address + " " + history) if c not in {"Сейчас", "Малая"}]
        if not cities:
            cities = [c for c in CITY_LOOSE.findall(address + " " + history) if c not in {"Сейчас", "Малая"}]
        if cities:
            city = cities[0]
        city = {
            "Бельц": "Бельцы",
            "Ростов-на": "Ростов-на-Дону",
            "Ростов-на Дону": "Ростов-на-Дону",
        }.get(city, city)
        if not city:
            city = NAME_CITY.get(name.split()[0].lower(), "")
        country_now, republic = "Россия", "РСФСР"
        hay = f"{address} {history}"
        for needle, country, old in COUNTRY_HINTS:
            if needle.lower() in hay.lower():
                country_now, republic = country, old
                break
        region = ""
        obl = re.search(r"([А-ЯЁ][А-Яа-яё\-]+(?:ая|ий|ой))\s+(обл\.|область|край|АО|АССР|республик\w*)", hay)
        if obl:
            region = f"{obl.group(1)} {obl.group(2).rstrip('.').replace('обл', 'область')}"
        quoted = QUOTED_RE.findall(name)
        short = quoted[0] if quoted else ""
        if not short:
            if "радиозавод" in name.lower():
                short = name.split(",")[0].replace(" радиозавод", " РЗ")
            else:
                short = name.split(",")[0]
        if len(short) > 48:
            short = short[:48].rstrip()
        kind = "institute" if re.search(r"НИИ|ВНИИ|СКБ|ЦКБ|\bКБ\b", name) else "factory"
        lat = lng = None
        if city in CITY_COORDS:
            lat, lng = CITY_COORDS[city]
        rows.append(
            {
                "name": name,
                "short_name": short,
                "city_then": city,
                "city_now": CITY_NOW.get(city, city),
                "republic": republic,
                "region": region,
                "country_now": country_now,
                "lat": lat,
                "lng": lng,
                "kind": kind,
                "description": history,
                "address": address,
                "products": " ".join(products),
                "keywords": keywords_for(name, short, city, quoted),
            }
        )
    return rows


def keywords_for(name: str, short: str, city: str, quoted: list[str]) -> list[str]:
    keys = []
    if city and city.lower() not in {
        "москва",
        "ленинград",
        "киев",
        "минск",
        "харьков",
        "рига",
        "горький",
        "санкт-петербург",
    }:
        keys.append(city.lower())
    for item in quoted:
        if len(item) > 2:
            keys.append(item.lower())
    core = re.sub(r"[«»\"(),./]", " ", name.lower())
    for word in core.split():
        if len(word) >= 6 and word not in {"завод", "завода", "радиозавод", "имени"}:
            keys.append(word)
    if short and len(short) > 3:
        keys.append(short.lower())
    # drop too-generic alone
    generic = {"радиоприбор", "электроприбор", "сигнал", "орбита"}
    return list(dict.fromkeys(k for k in keys if k and (k not in generic or city)))


def norm(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[«»\"'().,]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_existing(row: dict, factories) -> object | None:
    alias = ALIASES.get(norm(row["name"]))
    if alias:
        hit = next((f for f in factories if f.name == alias), None)
        if hit:
            return hit
    n = norm(row["name"])
    for factory in factories:
        fn = norm(factory.name)
        if fn == n:
            return factory
        if n in fn or fn in n:
            if len(min(n, fn, key=len)) >= 18:
                return factory
    return None


def import_db(rows: list[dict]) -> None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radiotsekh.settings")
    import django

    django.setup()

    from slugify import slugify as slugify_ru

    from catalog.management.commands.seed_catalog import make_slug, match_factories
    from catalog.models import Factory, Receiver

    used = set(Factory.objects.values_list("slug", flat=True))
    existing = list(Factory.objects.all())
    created = updated = 0
    for row in rows:
        factory = find_existing(row, existing)
        payload = {
            "short_name": row["short_name"],
            "city_then": row["city_then"],
            "city_now": row["city_now"],
            "republic": row["republic"],
            "region": row.get("region", ""),
            "country_now": row["country_now"],
            "kind": row["kind"],
        }
        if factory:
            for key, value in payload.items():
                if value and not getattr(factory, key):
                    setattr(factory, key, value)
            if row["description"] and (
                not factory.description or factory.description.startswith(factory.name + " —")
            ):
                factory.description = row["description"]
            if factory.lat is None and row["lat"] is not None:
                factory.lat, factory.lng = row["lat"], row["lng"]
            factory.save()
            updated += 1
        else:
            factory = Factory.objects.create(
                name=row["name"],
                slug=make_slug(row["short_name"] or row["name"], used),
                lat=row["lat"],
                lng=row["lng"],
                description=row["description"],
                **payload,
            )
            existing.append(factory)
            created += 1
    factories = list(Factory.objects.all())
    keywords = {}
    raw_old = json.loads((DATA / "factories.json").read_text(encoding="utf-8"))
    by_old = {item["name"]: item for item in raw_old}
    by_new = {item["name"]: item for item in rows}
    for factory in factories:
        keys = []
        if factory.name in by_old:
            keys.extend(by_old[factory.name].get("keywords") or [])
        if factory.name in by_new:
            keys.extend(by_new[factory.name].get("keywords") or [])
        if factory.short_name:
            keys.append(factory.short_name.lower())
        if factory.city_then:
            keys.append(factory.city_then.lower())
        keywords[factory.pk] = list(dict.fromkeys(k.lower() for k in keys if k))

    Receiver.factories.through.objects.all().delete()
    conservative = {}
    generic_short = {
        "гарни", "звезда", "анстрем", "стелла", "точмаш", "магнит", "мезон",
        "волна", "искра", "сигнал", "орбита", "радуга", "сокол", "луч", "маяк",
        "темп", "старт", "квант", "спектр", "фотон", "протон", "нептун", "алмаз",
        "прибор", "экран", "калибр", "зенит", "спутник", "россия", "аврора",
        "октава", "ротор", "сириус", "полёт", "полет", "вега", "рекорд", "тайфун",
        "нур", "ани", "элиа", "мир", "луч", "авест",
    }
    for factory in factories:
        keys = []
        if factory.name in by_old:
            keys.extend(k.lower() for k in (by_old[factory.name].get("keywords") or []))
        keys.append(norm(factory.name))
        if factory.city_then and "радиозавод" in factory.name.lower():
            keys.append(f"{factory.city_then.lower()} радиозавод")
        kept = []
        for key in keys:
            if not key or key in generic_short:
                continue
            if len(key) < 5 and factory.name not in by_old:
                continue
            kept.append(key)
        conservative[factory.pk] = list(dict.fromkeys(kept))

    linked = 0
    for receiver in Receiver.objects.all():
        text = " ".join(part for part in (receiver.description, receiver.notes) if part)
        if not text:
            continue
        found = match_factories(text, factories, conservative)
        if found:
            receiver.factories.set(found)
            linked += 1
    print(f"factories created={created} updated={updated} total={Factory.objects.count()} receivers_linked={linked}")


def main() -> None:
    if not PDF_PATH.exists():
        print("download pdf", PDF_URL)
        PDF_PATH.write_bytes(fetch(PDF_URL))
    text = pdf_text(PDF_PATH)
    rows = parse_blocks(text)
    JSON_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unknown = sorted({row["city_then"] for row in rows if row["city_then"] and row["lat"] is None})
    print(f"parsed {len(rows)} factories, cities without coords: {len(unknown)}")
    if unknown:
        print("  ", ", ".join(unknown[:40]))
    if "--parse-only" in sys.argv:
        return
    import_db(rows)


if __name__ == "__main__":
    main()
