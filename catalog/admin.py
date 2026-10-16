from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.utils.html import format_html

from catalog.models import Article, Band, Book, Chip, ChipType, Factory, PCBFile, PCBPhoto, Receiver, ReceiverCategory
from radiotsekh.admin import CompactAdmin


class CategoryTabFilter(admin.SimpleListFilter):
    title = "категория"
    parameter_name = "category"
    template = "admin/empty_filter.html"

    def lookups(self, request, model_admin):
        return [(str(category.pk), category.short_name) for category in ReceiverCategory.objects.order_by("sort_order")]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "none":
            return queryset.filter(category__isnull=True)
        if value and value != "all":
            return queryset.filter(category_id=value)
        return queryset


class CategoryRelatedFactoryFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        receivers = Receiver.objects.all()
        category = request.GET.get("category")
        if category == "none":
            receivers = receivers.filter(category__isnull=True)
        elif category and category.isdigit():
            receivers = receivers.filter(category_id=int(category))
        factory_ids = receivers.values_list("factories", flat=True).distinct()
        ordering = self.field_admin_ordering(field, request, model_admin)
        return field.get_choices(
            include_blank=False,
            limit_choices_to={"pk__in": factory_ids},
            ordering=ordering,
        )


@admin.register(Factory)
class FactoryAdmin(CompactAdmin):
    list_display = ("short_name", "name", "city_then", "republic", "country_now", "kind", "receiver_count")
    list_display_links = ("short_name", "name")
    list_filter = ("kind", "republic", "country_now")
    search_fields = ("name", "short_name", "city_then", "region")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("short_name",)
    fieldsets = (
        (None, {"fields": ("name", "short_name", "slug", "kind")}),
        (
            "Место",
            {
                "fields": (
                    ("city_then", "republic", "region"),
                    ("city_now", "country_now"),
                    ("lat", "lng"),
                )
            },
        ),
        ("Описание", {"fields": ("description",)}),
    )

    class Media:
        js = ("admin/js/factory_place.js",)

    @admin.display(description="Моделей", ordering="receiver_count")
    def receiver_count(self, obj):
        return obj.receiver_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(receiver_count=Count("receivers"))


@admin.register(Band)
class BandAdmin(CompactAdmin):
    list_display = ("code", "name")


@admin.register(ReceiverCategory)
class ReceiverCategoryAdmin(CompactAdmin):
    list_display = ("short_name", "name", "sort_order", "is_visible", "has_photo", "receiver_count")
    list_display_links = ("short_name", "name")
    list_editable = ("sort_order", "is_visible")
    list_filter = ("is_visible",)
    prepopulated_fields = {"slug": ("short_name",)}
    ordering = ("sort_order",)
    fields = ("name", "short_name", "slug", "code", "sort_order", "is_visible", "photo")

    @admin.display(description="Фото", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo)

    @admin.display(description="Моделей", ordering="receiver_count")
    def receiver_count(self, obj):
        return obj.receiver_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(receiver_count=Count("receivers"))


class ReceiverPCBInline(admin.TabularInline):
    model = PCBFile.receivers.through
    extra = 0
    autocomplete_fields = ("pcbfile",)
    verbose_name = "печатная плата"
    verbose_name_plural = "печатные платы"


@admin.register(Receiver)
class ReceiverAdmin(CompactAdmin):
    list_display = (
        "name",
        "category",
        "years_display",
        "produced_count",
        "factory_names",
        "band_codes",
        "has_photo",
        "has_drawing",
        "has_manual",
        "pcb_count",
        "is_featured",
        "is_prototype",
        "is_hidden",
    )
    list_display_links = ("name",)
    list_editable = ("is_featured", "is_hidden")
    list_filter = (
        CategoryTabFilter,
        "is_prototype",
        "is_featured",
        "is_hidden",
        "bands",
        ("factories", CategoryRelatedFactoryFilter),
    )
    search_fields = ("name", "description", "notes")
    filter_horizontal = ("factories", "bands")
    prepopulated_fields = {"slug": ("name",)}
    exclude = ("source_url",)
    list_select_related = ("category",)
    view_on_site = True
    list_prefetch_related = ("factories", "bands")
    inlines = [ReceiverPCBInline]
    list_per_page = 100

    class Media:
        js = ("admin/js/receiver_hidden_toggle.js",)

    fieldsets = (
        (
            "Модель",
            {
                "fields": (
                    ("name", "slug"),
                    "category",
                    ("year_start", "year_end", "produced_count"),
                    ("is_prototype", "is_featured", "is_hidden"),
                )
            },
        ),
        (
            "Фото и файлы",
            {
                "fields": ("photo", "board_drawing", "manual"),
                "description": "Фото карточки, рисунок платы (PDF/DJVU/JPG) и инструкция.",
            },
        ),
        ("Заводы и диапазоны", {"fields": ("factories", "bands", "bands_note")}),
        ("Описание", {"fields": ("description", "notes")}),
        (
            "Характеристики",
            {
                "fields": (
                    "sensitivity",
                    "selectivity",
                    "output_power",
                    "frequency_response",
                    "power_supply",
                    ("dimensions", "weight"),
                    ("transistor_count", "receiver_class", "original_price"),
                )
            },
        ),
        ("Связанные материалы", {"fields": ("related_content",)}),
    )
    readonly_fields = ("related_content",)

    @admin.display(description="Статьи, книги, товары")
    def related_content(self, obj):
        if not obj.pk:
            return "—"
        articles = ", ".join(obj.articles.values_list("title", flat=True)) or "—"
        books = ", ".join(obj.books.values_list("title", flat=True)) or "—"
        products = ", ".join(obj.products.values_list("title", flat=True)) or "—"
        return format_html(
            "<p><b>Статьи:</b> {}</p><p><b>Книги:</b> {}</p><p><b>Товары:</b> {}</p>",
            articles,
            books,
            products,
        )

    @admin.display(description="Годы", ordering="year_start")
    def years_display(self, obj):
        return obj.years_display or "—"

    @admin.display(description="Заводы")
    def factory_names(self, obj):
        names = [factory.short_name or factory.name for factory in obj.factories.all()]
        return ", ".join(names) or "—"

    @admin.display(description="Диапазоны")
    def band_codes(self, obj):
        return " ".join(band.code for band in obj.bands.all()) or "—"

    @admin.display(description="Фото", boolean=True)
    def has_photo(self, obj):
        return bool(obj.photo)

    @admin.display(description="Рисунок", boolean=True)
    def has_drawing(self, obj):
        return bool(obj.board_drawing)

    @admin.display(description="Инструкция", boolean=True)
    def has_manual(self, obj):
        return bool(obj.manual)

    @admin.display(description="LAY")
    def pcb_count(self, obj):
        return obj.pcb_count

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("factories", "bands")
            .annotate(pcb_count=Count("pcb_files", distinct=True))
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if "category" not in request.GET and not request.GET.get("q"):
            first = ReceiverCategory.objects.order_by("sort_order").first()
            if first:
                params = request.GET.copy()
                params["category"] = str(first.pk)
                return HttpResponseRedirect(f"{request.path}?{params.urlencode()}")
        extra_context.update(self._category_tabs(request))
        return super().changelist_view(request, extra_context=extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj and obj.category_id:
            context["site_edit_url"] = obj.get_edit_url()
        return super().render_change_form(request, context, add, change, form_url, obj)

    def _category_tabs(self, request):
        params = request.GET.copy()
        params.pop("p", None)
        current = request.GET.get("category", "all")
        tabs = []
        for category in ReceiverCategory.objects.annotate(n=Count("receivers")).order_by("sort_order"):
            params["category"] = str(category.pk)
            tabs.append(
                {
                    "label": category.short_name,
                    "count": category.n,
                    "query": params.urlencode(),
                    "active": current == str(category.pk),
                }
            )
        uncategorized = Receiver.objects.filter(category__isnull=True).count()
        if uncategorized:
            params["category"] = "none"
            tabs.append(
                {
                    "label": "Без категории",
                    "count": uncategorized,
                    "query": params.urlencode(),
                    "active": current == "none",
                }
            )
        params["category"] = "all"
        return {
            "category_tabs": tabs,
            "all_tab": {
                "label": "Все",
                "count": Receiver.objects.count(),
                "query": params.urlencode(),
                "active": current == "all",
            },
        }

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        category_id = request.GET.get("category")
        if category_id and category_id.isdigit():
            initial.setdefault("category", int(category_id))
        return initial


@admin.register(Article)
class ArticleAdmin(CompactAdmin):
    list_display = ("title", "published_at", "has_original", "receiver_names")
    list_display_links = ("title",)
    search_fields = ("title", "body")
    list_filter = ("published_at",)
    filter_horizontal = ("receivers",)
    prepopulated_fields = {"slug": ("title",)}
    list_prefetch_related = ("receivers",)
    fields = ("title", "slug", "excerpt", "body", "original_file", "published_at", "receivers")

    @admin.display(description="Оригинал", boolean=True)
    def has_original(self, obj):
        return bool(obj.original_file)

    @admin.display(description="Модели")
    def receiver_names(self, obj):
        return ", ".join(obj.receivers.values_list("name", flat=True)[:6]) or "—"


@admin.register(Book)
class BookAdmin(CompactAdmin):
    list_display = ("title", "authors", "year", "publisher", "receiver_names")
    list_display_links = ("title",)
    search_fields = ("title", "authors")
    list_filter = ("year",)
    filter_horizontal = ("receivers",)
    prepopulated_fields = {"slug": ("title",)}
    list_prefetch_related = ("receivers",)

    @admin.display(description="Модели")
    def receiver_names(self, obj):
        return ", ".join(obj.receivers.values_list("name", flat=True)[:6]) or "—"


@admin.register(ChipType)
class ChipTypeAdmin(CompactAdmin):
    list_display = ("name", "sort_order", "chip_count")
    list_display_links = ("name",)
    list_editable = ("sort_order",)
    search_fields = ("name",)
    ordering = ("sort_order", "name")

    @admin.display(description="Микросхем", ordering="chip_count")
    def chip_count(self, obj):
        return obj.chip_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(chip_count=Count("chips"))


@admin.register(Chip)
class ChipAdmin(CompactAdmin):
    list_display = ("name", "chip_type", "manufacturer", "notes", "board_count")
    list_display_links = ("name",)
    list_filter = ("chip_type",)
    list_editable = ("chip_type",)
    search_fields = ("name", "manufacturer", "notes", "chip_type__name")
    list_select_related = ("chip_type",)
    fields = ("name", "chip_type", "manufacturer", "notes")

    @admin.display(description="Плат", ordering="board_count")
    def board_count(self, obj):
        return obj.board_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(board_count=Count("pcb_files"))


class PCBPhotoInline(admin.TabularInline):
    model = PCBPhoto
    extra = 1


@admin.register(PCBFile)
class PCBFileAdmin(CompactAdmin):
    list_display = ("title", "receiver_names", "chip_names", "kind", "developed_at", "version", "is_free", "file_name")
    list_display_links = ("title",)
    list_editable = ("kind", "is_free")
    list_filter = ("kind", "is_free", "chips", "developed_at")
    search_fields = ("title", "notes", "author_name", "author__username", "receivers__name", "chips__name", "chips__chip_type__name")
    filter_horizontal = ("receivers", "chips")
    list_prefetch_related = ("receivers", "chips")
    autocomplete_fields = ("created_by", "author")
    date_hierarchy = "developed_at"
    inlines = [PCBPhotoInline]
    fields = (
        "title",
        "kind",
        "file",
        "version",
        "developed_at",
        "source_url",
        "author_name",
        "author",
        "notes",
        "is_free",
        "receivers",
        "chips",
        "created_by",
    )

    @admin.display(description="Приёмники")
    def receiver_names(self, obj):
        return ", ".join(obj.receivers.values_list("name", flat=True)[:6]) or "—"

    @admin.display(description="Микросхемы")
    def chip_names(self, obj):
        return ", ".join(obj.chips.values_list("name", flat=True)[:6]) or "—"

    @admin.display(description="Файл")
    def file_name(self, obj):
        if not obj.file:
            return "—"
        name = obj.file.name.rsplit("/", 1)[-1]
        return format_html('<a href="{}">{}</a>', obj.file.url, name)
