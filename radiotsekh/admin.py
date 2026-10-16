from django.contrib import admin
from django.db.models import Count


class CompactAdmin(admin.ModelAdmin):
    list_per_page = 75
    list_max_show_all = 400
    save_on_top = True
    empty_value_display = "—"
    show_full_result_count = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        prefetch = getattr(self, "list_prefetch_related", ())
        select = getattr(self, "list_select_related", False)
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        if select and select is not True:
            qs = qs.select_related(*select)
        return qs
