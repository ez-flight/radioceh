from django.contrib import admin
from django.db.models import Count

from radiotsekh.admin import CompactAdmin
from shop.models import Order, OrderItem, Product


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product",)
    fields = ("product", "quantity", "price")


@admin.register(Product)
class ProductAdmin(CompactAdmin):
    list_display = ("title", "kind", "price", "stock", "is_active", "receiver", "pcb_count")
    list_display_links = ("title",)
    list_editable = ("price", "stock", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "description", "receiver__name")
    filter_horizontal = ("pcb_files",)
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("receiver",)
    autocomplete_fields = ("receiver",)

    @admin.display(description="LAY", ordering="pcb_count")
    def pcb_count(self, obj):
        return obj.pcb_count

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("receiver").annotate(pcb_count=Count("pcb_files"))


@admin.register(Order)
class OrderAdmin(CompactAdmin):
    list_display = ("id", "customer_name", "email", "phone", "status", "total", "item_count", "created_at")
    list_display_links = ("id", "customer_name")
    list_editable = ("status",)
    list_filter = ("status", "created_at")
    search_fields = ("customer_name", "email", "phone")
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"

    @admin.display(description="Позиций", ordering="item_count")
    def item_count(self, obj):
        return obj.item_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(item_count=Count("items"))
