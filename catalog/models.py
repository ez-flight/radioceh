from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from catalog.storage import PrivateStorage

DRAWING_EXTENSIONS = ("pdf", "djvu", "djv", "jpg", "jpeg", "png", "webp")
DOCUMENT_EXTENSIONS = ("pdf", "djvu", "djv")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


class Factory(models.Model):
    class Kind(models.TextChoices):
        FACTORY = "factory", "Завод"
        INSTITUTE = "institute", "Институт"

    class Republic(models.TextChoices):
        RSFSR = "РСФСР", "РСФСР"
        UKRAINIAN = "Украинская ССР", "Украинская ССР"
        BELARUSIAN = "Белорусская ССР", "Белорусская ССР"
        UZBEK = "Узбекская ССР", "Узбекская ССР"
        KAZAKH = "Казахская ССР", "Казахская ССР"
        GEORGIAN = "Грузинская ССР", "Грузинская ССР"
        AZERBAIJANI = "Азербайджанская ССР", "Азербайджанская ССР"
        LITHUANIAN = "Литовская ССР", "Литовская ССР"
        MOLDAVIAN = "Молдавская ССР", "Молдавская ССР"
        LATVIAN = "Латвийская ССР", "Латвийская ССР"
        KYRGYZ = "Киргизская ССР", "Киргизская ССР"
        TAJIK = "Таджикская ССР", "Таджикская ССР"
        ARMENIAN = "Армянская ССР", "Армянская ССР"
        TURKMEN = "Туркменская ССР", "Туркменская ССР"
        ESTONIAN = "Эстонская ССР", "Эстонская ССР"

    class CountryNow(models.TextChoices):
        RUSSIA = "Россия", "Россия"
        UKRAINE = "Украина", "Украина"
        BELARUS = "Беларусь", "Беларусь"
        UZBEKISTAN = "Узбекистан", "Узбекистан"
        KAZAKHSTAN = "Казахстан", "Казахстан"
        GEORGIA = "Грузия", "Грузия"
        AZERBAIJAN = "Азербайджан", "Азербайджан"
        LITHUANIA = "Литва", "Литва"
        MOLDOVA = "Молдова", "Молдова"
        LATVIA = "Латвия", "Латвия"
        KYRGYZSTAN = "Кыргызстан", "Кыргызстан"
        TAJIKISTAN = "Таджикистан", "Таджикистан"
        ARMENIA = "Армения", "Армения"
        TURKMENISTAN = "Туркменистан", "Туркменистан"
        ESTONIA = "Эстония", "Эстония"

    REPUBLIC_TO_COUNTRY = {
        Republic.RSFSR: CountryNow.RUSSIA,
        Republic.UKRAINIAN: CountryNow.UKRAINE,
        Republic.BELARUSIAN: CountryNow.BELARUS,
        Republic.UZBEK: CountryNow.UZBEKISTAN,
        Republic.KAZAKH: CountryNow.KAZAKHSTAN,
        Republic.GEORGIAN: CountryNow.GEORGIA,
        Republic.AZERBAIJANI: CountryNow.AZERBAIJAN,
        Republic.LITHUANIAN: CountryNow.LITHUANIA,
        Republic.MOLDAVIAN: CountryNow.MOLDOVA,
        Republic.LATVIAN: CountryNow.LATVIA,
        Republic.KYRGYZ: CountryNow.KYRGYZSTAN,
        Republic.TAJIK: CountryNow.TAJIKISTAN,
        Republic.ARMENIAN: CountryNow.ARMENIA,
        Republic.TURKMEN: CountryNow.TURKMENISTAN,
        Republic.ESTONIAN: CountryNow.ESTONIA,
    }

    name = models.CharField("Название", max_length=220, unique=True)
    short_name = models.CharField("Краткое имя", max_length=80, blank=True)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    city_then = models.CharField("Город (тогда)", max_length=120, blank=True)
    republic = models.CharField("Республика СССР", max_length=40, choices=Republic.choices, blank=True)
    region = models.CharField("Область / край", max_length=180, blank=True)
    country_now = models.CharField("Страна сейчас", max_length=40, choices=CountryNow.choices, blank=True)
    city_now = models.CharField("Город сейчас", max_length=120, blank=True)
    lat = models.FloatField("Широта", null=True, blank=True)
    lng = models.FloatField("Долгота", null=True, blank=True)
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices, default=Kind.FACTORY)
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "завод"
        verbose_name_plural = "заводы"
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name

    def get_absolute_url(self):
        return reverse("catalog:factory_detail", args=[self.slug])


class Band(models.Model):
    code = models.CharField("Код", max_length=8, unique=True)
    name = models.CharField("Название", max_length=80)

    class Meta:
        verbose_name = "диапазон"
        verbose_name_plural = "диапазоны"
        ordering = ["id"]

    def __str__(self):
        return self.code


class ReceiverCategory(models.Model):
    name = models.CharField("Название", max_length=160, unique=True)
    short_name = models.CharField("Краткое имя", max_length=80)
    slug = models.SlugField("Слаг", max_length=160, unique=True)
    code = models.SlugField("Код", max_length=40, unique=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    is_visible = models.BooleanField("Показывать на сайте", default=True)
    photo = models.ImageField("Фото категории", upload_to="covers/categories/", blank=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.short_name or self.name

    def get_absolute_url(self):
        return reverse("catalog:receiver_list", args=[self.slug])


class Receiver(models.Model):
    name = models.CharField("Модель", max_length=180)
    slug = models.SlugField("Слаг", max_length=200, unique=True)
    category = models.ForeignKey(
        "ReceiverCategory",
        verbose_name="Категория",
        related_name="receivers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    year_start = models.PositiveSmallIntegerField("Начало выпуска", null=True, blank=True)
    year_end = models.PositiveSmallIntegerField("Конец выпуска", null=True, blank=True)
    produced_count = models.PositiveIntegerField("Выпущено, шт.", null=True, blank=True)
    is_prototype = models.BooleanField("Опытный", default=False)
    is_hidden = models.BooleanField("Скрыть", default=False)
    factories = models.ManyToManyField(Factory, verbose_name="Заводы", blank=True, related_name="receivers")
    bands = models.ManyToManyField(Band, verbose_name="Диапазоны", blank=True, related_name="receivers")
    bands_note = models.CharField("Уточнение диапазонов", max_length=180, blank=True)
    description = models.TextField("Описание", blank=True)
    notes = models.TextField("Примечание", blank=True)
    source_url = models.URLField("Карточка источника", blank=True)
    photo = models.ImageField("Фото карточки", upload_to="covers/receivers/", blank=True)
    board_drawing = models.FileField(
        "Рисунок платы",
        upload_to="receivers/drawings/",
        blank=True,
        validators=[FileExtensionValidator(DRAWING_EXTENSIONS)],
        help_text="PDF, DJVU или JPG/PNG",
    )
    manual = models.FileField(
        "Инструкция",
        upload_to="receivers/manuals/",
        blank=True,
        validators=[FileExtensionValidator(DOCUMENT_EXTENSIONS + ("jpg", "jpeg", "png"))],
        help_text="PDF, DJVU или скан JPG/PNG",
    )
    sensitivity = models.CharField("Чувствительность", max_length=160, blank=True)
    selectivity = models.CharField("Избирательность", max_length=160, blank=True)
    output_power = models.CharField("Выходная мощность", max_length=120, blank=True)
    frequency_response = models.CharField("Полоса частот", max_length=120, blank=True)
    power_supply = models.CharField("Питание", max_length=160, blank=True)
    dimensions = models.CharField("Габариты", max_length=80, blank=True)
    weight = models.CharField("Масса", max_length=40, blank=True)
    original_price = models.CharField("Цена в СССР", max_length=80, blank=True)
    receiver_class = models.CharField("Класс", max_length=20, blank=True)
    transistor_count = models.PositiveSmallIntegerField("Транзисторов", null=True, blank=True)
    is_featured = models.BooleanField("На главной", default=False)

    class Meta:
        verbose_name = "приёмник"
        verbose_name_plural = "приёмники"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        if self.category_id:
            return reverse("catalog:receiver_detail", args=[self.category.slug, self.slug])
        return reverse("catalog:catalog_index")

    def get_edit_url(self):
        if self.category_id:
            return reverse("catalog:receiver_edit", args=[self.category.slug, self.slug])
        return ""

    def _is_image(self, field):
        name = getattr(field, "name", "")
        return bool(name) and name.lower().endswith(IMAGE_EXTENSIONS)

    @property
    def drawing_is_image(self):
        return self._is_image(self.board_drawing)

    @property
    def decade(self):
        if not self.year_start:
            return None
        return (self.year_start // 10) * 10

    @property
    def years_display(self):
        start, end = self.year_start, self.year_end
        if start and end and end != start:
            return f"{start}–{end}"
        if start and end:
            return str(start)
        if start:
            return f"с {start}"
        if end:
            return f"до {end}"
        return ""


class Article(models.Model):
    title = models.CharField("Заголовок", max_length=220)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    excerpt = models.TextField("Лид", blank=True)
    body = models.TextField("Текст", blank=True)
    original_file = models.FileField(
        "Оригинал статьи",
        upload_to="articles/",
        blank=True,
        validators=[FileExtensionValidator(DOCUMENT_EXTENSIONS + ("jpg", "jpeg", "png", "webp"))],
        help_text="PDF, DJVU или JPG/PNG",
    )
    published_at = models.DateField("Дата")
    receivers = models.ManyToManyField(Receiver, verbose_name="Приёмники", blank=True, related_name="articles")

    class Meta:
        verbose_name = "статья"
        verbose_name_plural = "статьи"
        ordering = ["-published_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:article_detail", args=[self.slug])


class Book(models.Model):
    title = models.CharField("Название", max_length=220)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    authors = models.CharField("Авторы", max_length=220)
    year = models.PositiveSmallIntegerField("Год", null=True, blank=True)
    publisher = models.CharField("Издательство", max_length=160, blank=True)
    description = models.TextField("Описание", blank=True)
    receivers = models.ManyToManyField(Receiver, verbose_name="Приёмники", blank=True, related_name="books")

    class Meta:
        verbose_name = "книга"
        verbose_name_plural = "книги"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:book_detail", args=[self.slug])


class ChipType(models.Model):
    name = models.CharField("Название", max_length=80, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "тип микросхемы"
        verbose_name_plural = "типы микросхем"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Chip(models.Model):
    name = models.CharField("Маркировка", max_length=80, unique=True)
    chip_type = models.ForeignKey(
        ChipType,
        verbose_name="Тип",
        related_name="chips",
        on_delete=models.PROTECT,
    )
    manufacturer = models.CharField("Производитель", max_length=120, blank=True)
    notes = models.CharField("Примечание", max_length=220, blank=True)

    class Meta:
        verbose_name = "микросхема"
        verbose_name_plural = "микросхемы"
        ordering = ["chip_type", "name"]

    def __str__(self):
        return f"{self.name} — {self.chip_type}"


class PCBFile(models.Model):
    class Kind(models.TextChoices):
        ORIGINAL = "original", "Оригинальная плата"
        MODERN = "modern", "Плата на современной элементной базе"

    title = models.CharField("Название", max_length=220)
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices)
    file = models.FileField(
        "Файл платы",
        upload_to="pcb/",
        storage=PrivateStorage(),
        validators=[FileExtensionValidator(("lay", "lay6", "pcb", "zip", "pdf"))],
        help_text="LAY, LAY6, PCB, ZIP или PDF",
    )
    version = models.CharField("Версия", max_length=40, blank=True)
    notes = models.TextField("Комментарий", blank=True)
    developed_at = models.DateField("Дата разработки", default=timezone.localdate)
    is_free = models.BooleanField("Бесплатно", default=False)
    receivers = models.ManyToManyField(
        Receiver, verbose_name="Приёмники", related_name="pcb_files"
    )
    chips = models.ManyToManyField(
        "Chip", verbose_name="Микросхемы", blank=True, related_name="pcb_files"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Кто добавил",
        related_name="pcb_files",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_url = models.URLField(
        "Ссылка на статью",
        blank=True,
        help_text="Если плата скачана со стороннего ресурса.",
    )
    author_name = models.CharField(
        "Ник автора",
        max_length=80,
        blank=True,
        help_text="Ник с исходной статьи. Если автор зарегистрирован на сайте — укажите его логин.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Автор на сайте",
        related_name="authored_pcbs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "печатная плата"
        verbose_name_plural = "печатные платы"
        ordering = ["-developed_at", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:pcb_detail", args=[self.pk])

    @property
    def author_display(self):
        if self.author_id:
            return self.author.get_username()
        return self.author_name

    def can_access_file(self, user):
        """Бесплатные платы — всем; платные — персоналу и тому, кто их загрузил или разработал."""
        if self.is_free:
            return True
        if not getattr(user, "is_authenticated", False):
            return False
        return user.is_staff or user.pk in (self.created_by_id, self.author_id)

    def can_review_file(self, user):
        """Замечания проверки видят персонал и тот, кто плату загрузил или разработал."""
        if not getattr(user, "is_authenticated", False):
            return False
        return user.is_staff or user.pk in (self.created_by_id, self.author_id)

    @property
    def is_lay(self):
        return self.file.name.lower().endswith((".lay", ".lay6"))

    def lay_analysis(self):
        """Сводка, цепи и проверка платы Sprint Layout или None, если файл не читается."""
        from catalog.lay import LayError
        from catalog.laytools import analyze_file

        if not self.file or not self.is_lay:
            return None
        try:
            return analyze_file(self.file.path)
        except (LayError, OSError, ValueError):
            return None

    def lay_svg_nets(self, with_markers=False):
        """SVG с разметкой цепей (data-net) и, по желанию, маркерами замечаний проверки."""
        from catalog.lay import LayError
        from catalog.laytools import svg_with_nets

        if not self.file or not self.is_lay:
            return None
        try:
            return svg_with_nets(self.file.path, with_markers)
        except (LayError, OSError, ValueError):
            return None

    def lay_svg(self):
        """SVG платы из файла Sprint Layout или None, если файл не читается."""
        from catalog.lay import LayError, render_file

        if not self.file or not self.is_lay:
            return None
        try:
            return render_file(self.file.path)
        except (LayError, OSError):
            return None


class PCBPhoto(models.Model):
    pcb = models.ForeignKey(
        PCBFile,
        verbose_name="Плата",
        related_name="photos",
        on_delete=models.CASCADE,
    )
    image = models.ImageField("Фото", upload_to="pcb/photos/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "фото проекта"
        verbose_name_plural = "фото проекта"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.image.name.rsplit("/", 1)[-1]
