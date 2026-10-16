from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from catalog.forms import PCBUploadForm, ReceiverEditForm
from catalog.models import Article, Book, Factory, PCBFile, PCBPhoto, Receiver, ReceiverCategory
from catalog.permissions import can_edit_catalog, can_upload_boards
from shop.models import Product


def visible_receivers():
    return Receiver.objects.filter(category__is_visible=True, is_hidden=False)


def category_receivers(user, category_slug):
    qs = Receiver.objects.filter(category__slug=category_slug)
    if not can_edit_catalog(user):
        qs = qs.filter(category__is_visible=True, is_hidden=False)
    return qs


class HomeView(TemplateView):
    template_name = "catalog/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["featured"] = (
            visible_receivers().filter(is_featured=True).prefetch_related("factories", "bands")[:8]
        )
        ctx["stats"] = {
            "receivers": visible_receivers().count(),
            "factories": Factory.objects.filter(kind=Factory.Kind.FACTORY).count(),
            "pcbs": PCBFile.objects.count(),
            "articles": Article.objects.count(),
        }
        ctx["latest_articles"] = Article.objects.prefetch_related("receivers")[:3]
        ctx["products"] = Product.objects.filter(is_active=True).select_related("receiver__category")[:4]
        return ctx


class CatalogIndexView(ListView):
    model = ReceiverCategory
    template_name = "catalog/catalog_index.html"
    context_object_name = "categories"

    def get_queryset(self):
        return (
            ReceiverCategory.objects.filter(is_visible=True)
            .annotate(n=Count("receivers", filter=Q(receivers__is_hidden=False)))
            .order_by("sort_order")
        )


class ReceiverListView(ListView):
    model = Receiver
    paginate_by = 24
    template_name = "catalog/receiver_list.html"
    context_object_name = "receivers"

    def get_category(self):
        return get_object_or_404(ReceiverCategory, slug=self.kwargs["category_slug"], is_visible=True)

    def get_queryset(self):
        qs = (
            visible_receivers()
            .filter(category=self.get_category())
            .select_related("category")
            .prefetch_related("factories", "bands")
        )
        q = self.request.GET.get("q", "").strip()
        factory = self.request.GET.get("factory")
        band = self.request.GET.get("band")
        decade = self.request.GET.get("decade")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(notes__icontains=q)
                | Q(factories__name__icontains=q)
                | Q(factories__short_name__icontains=q)
            ).distinct()
        if factory:
            qs = qs.filter(factories__slug=factory)
        if band:
            qs = qs.filter(bands__code=band)
        if decade and decade.isdigit():
            start = int(decade)
            qs = qs.filter(year_start__gte=start, year_start__lt=start + 10)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_category"] = self.get_category()
        ctx["factories"] = Factory.objects.annotate(n=Count("receivers")).filter(n__gt=0)
        ctx["bands"] = (
            Receiver.objects.values("bands__code", "bands__name")
            .exclude(bands__code=None)
            .annotate(n=Count("id"))
            .order_by("bands__id")
        )
        years = (
            visible_receivers()
            .filter(category=self.get_category())
            .exclude(year_start=None)
            .values_list("year_start", flat=True)
        )
        ctx["decades"] = sorted({(year // 10) * 10 for year in years})
        ctx["filters"] = self.request.GET
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["query"] = params.urlencode()
        return ctx


class ReceiverDetailView(DetailView):
    model = Receiver
    template_name = "catalog/receiver_detail.html"
    context_object_name = "receiver"

    def get_queryset(self):
        return (
            category_receivers(self.request.user, self.kwargs["category_slug"])
            .select_related("category")
            .prefetch_related(
                "factories",
                "bands",
                "articles",
                "books",
                "pcb_files__chips__chip_type",
                Prefetch("products", queryset=Product.objects.filter(is_active=True)),
            )
        )


class ReceiverUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Receiver
    form_class = ReceiverEditForm
    template_name = "catalog/receiver_edit.html"
    context_object_name = "receiver"

    def test_func(self):
        return can_edit_catalog(self.request.user)

    def get_queryset(self):
        return (
            Receiver.objects.filter(category__slug=self.kwargs["category_slug"])
            .select_related("category")
            .prefetch_related("factories", "bands")
        )

    def form_valid(self, form):
        messages.success(self.request, "Карточка приёмника сохранена.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_edit_url() or reverse(
            "admin:catalog_receiver_change", args=[self.object.pk]
        )


class FactoryListView(ListView):
    model = Factory
    template_name = "catalog/factory_list.html"
    context_object_name = "factories"

    def get_queryset(self):
        return (
            Factory.objects.annotate(
                receiver_count=Count(
                    "receivers",
                    filter=Q(receivers__category__is_visible=True, receivers__is_hidden=False),
                    distinct=True,
                )
            )
            .filter(receiver_count__gt=0, lat__isnull=False, lng__isnull=False)
            .order_by("country_now", "city_then", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["factory_points"] = [
            {
                "name": factory.short_name or factory.name,
                "lat": factory.lat,
                "lng": factory.lng,
                "url": factory.get_absolute_url(),
            }
            for factory in ctx["factories"]
        ]
        return ctx


class FactoryDetailView(DetailView):
    model = Factory
    template_name = "catalog/factory_detail.html"
    context_object_name = "factory"

    def get_queryset(self):
        return Factory.objects.prefetch_related(
            Prefetch(
                "receivers",
                queryset=visible_receivers().select_related("category").prefetch_related("bands"),
            )
        )


class ArticleListView(ListView):
    model = Article
    paginate_by = 12
    template_name = "catalog/article_list.html"
    context_object_name = "articles"


class ArticleDetailView(DetailView):
    model = Article
    template_name = "catalog/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        return Article.objects.prefetch_related("receivers")


class BookListView(ListView):
    model = Book
    template_name = "catalog/book_list.html"
    context_object_name = "books"


class BookDetailView(DetailView):
    model = Book
    template_name = "catalog/book_detail.html"
    context_object_name = "book"

    def get_queryset(self):
        return Book.objects.prefetch_related("receivers")


class DocumentViewerView(DetailView):
    template_name = "catalog/document_viewer.html"
    file_field = ""
    doc_title = ""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not getattr(obj, self.file_field):
            raise Http404("Файл не найден.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["object"]
        ctx["file"] = getattr(obj, self.file_field)
        ctx["title"] = f"{self.doc_title} — {obj}"
        return ctx


class ReceiverManualView(DocumentViewerView):
    model = Receiver
    context_object_name = "receiver"
    file_field = "manual"
    doc_title = "Инструкция"

    def get_queryset(self):
        return visible_receivers().filter(category__slug=self.kwargs["category_slug"]).select_related("category")


class ReceiverDrawingView(DocumentViewerView):
    model = Receiver
    context_object_name = "receiver"
    file_field = "board_drawing"
    doc_title = "Рисунок платы"

    def get_queryset(self):
        return visible_receivers().filter(category__slug=self.kwargs["category_slug"]).select_related("category")


class ArticleOriginalView(DocumentViewerView):
    model = Article
    context_object_name = "article"
    file_field = "original_file"
    doc_title = "Оригинал"
    slug_url_kwarg = "slug"


class PCBPreviewView(DocumentViewerView):
    model = PCBFile
    context_object_name = "pcb"
    file_field = "file"
    doc_title = "Файл платы"

    def get_object(self, queryset=None):
        return get_accessible_pcb(self.request, self.kwargs["pk"])

    def get_template_names(self):
        if self.object.is_lay:
            return ["catalog/pcb_viewer.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.object.is_lay:
            ctx["svg"] = self.object.lay_svg()
        return ctx


def get_accessible_pcb(request, pk=None, file_name=None):
    """Плата, к файлу которой у пользователя есть доступ; иначе 404, чтобы не выдавать платные файлы."""
    lookup = {"pk": pk} if pk is not None else {"file": file_name}
    pcb = PCBFile.objects.filter(**lookup).exclude(file="").first()
    if pcb is None or not pcb.can_access_file(request.user):
        raise Http404("Файл доступен после покупки проекта.")
    return pcb


def pcb_file_response(pcb, as_attachment):
    try:
        handle = pcb.file.open("rb")
    except FileNotFoundError:
        raise Http404("Файл не найден.")
    return FileResponse(handle, as_attachment=as_attachment, filename=pcb.file.name.rsplit("/", 1)[-1])


def pcb_file(request, path):
    """Файл платы по его имени в хранилище — для встроенного просмотра PDF и ссылок в админке."""
    return pcb_file_response(get_accessible_pcb(request, file_name=path), as_attachment=False)


def pcb_svg(request, pk):
    pcb = get_accessible_pcb(request, pk)
    svg = pcb.lay_svg()
    if svg is None:
        raise Http404("Не удалось прочитать файл платы.")
    return HttpResponse(svg, content_type="image/svg+xml; charset=utf-8")


class PCBListView(ListView):
    model = PCBFile
    paginate_by = 24
    template_name = "catalog/pcb_list.html"
    context_object_name = "pcbs"

    def get_queryset(self):
        qs = PCBFile.objects.select_related("author").prefetch_related(
            Prefetch("receivers", queryset=Receiver.objects.order_by("name")),
            "chips__chip_type",
            "photos",
        ).distinct()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(notes__icontains=q)
                | Q(author_name__icontains=q)
                | Q(author__username__icontains=q)
                | Q(receivers__name__icontains=q)
                | Q(chips__name__icontains=q)
                | Q(chips__chip_type__name__icontains=q)
            ).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filters"] = self.request.GET
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["query"] = params.urlencode()
        shop_only = (
            visible_receivers()
            .filter(products__is_active=True, pcb_files__isnull=True)
            .distinct()
            .order_by("name")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            shop_only = shop_only.filter(name__icontains=q)
        ctx["shop_only_receivers"] = shop_only
        return ctx


class PCBDetailView(DetailView):
    model = PCBFile
    template_name = "catalog/pcb_detail.html"
    context_object_name = "pcb"

    def get_queryset(self):
        return PCBFile.objects.select_related("author").prefetch_related(
            "receivers__category", "chips__chip_type", "products", "photos"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pcb = self.object
        ctx["can_access_file"] = pcb.can_access_file(self.request.user)
        ctx["lay_preview"] = ctx["can_access_file"] and pcb.lay_svg() is not None
        return ctx


class PCBCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = PCBFile
    form_class = PCBUploadForm
    template_name = "catalog/pcb_form.html"
    success_url = reverse_lazy("catalog:pcb_list")

    def test_func(self):
        return can_upload_boards(self.request.user)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        for index, photo in enumerate(form.cleaned_data.get("photos") or []):
            PCBPhoto.objects.create(pcb=self.object, image=photo, sort_order=index)
        messages.success(self.request, "Проект платы добавлен.")
        return response


def pcb_download(request, pk):
    return pcb_file_response(get_accessible_pcb(request, pk), as_attachment=True)


def about(request):
    return render(request, "catalog/about.html")


def redirect_old_library(request, rest=""):
    slug = rest.strip("/").split("/")[-1]
    receiver = (
        Receiver.objects.filter(slug=slug, category__is_visible=True, is_hidden=False)
        .select_related("category")
        .first()
    )
    if receiver and receiver.category_id:
        return redirect(receiver.get_absolute_url())
    return redirect("catalog:catalog_index")
