from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.CatalogIndexView.as_view(), name="catalog_index"),
    path("zavody/", views.FactoryListView.as_view(), name="factory_list"),
    path("zavody/<slug:slug>/", views.FactoryDetailView.as_view(), name="factory_detail"),
    path("stati/", views.ArticleListView.as_view(), name="article_list"),
    path("stati/<slug:slug>/original/", views.ArticleOriginalView.as_view(), name="article_original"),
    path("stati/<slug:slug>/", views.ArticleDetailView.as_view(), name="article_detail"),
    path("knigi/", views.BookListView.as_view(), name="book_list"),
    path("knigi/<slug:slug>/", views.BookDetailView.as_view(), name="book_detail"),
    path("platy/", views.PCBListView.as_view(), name="pcb_list"),
    path("platy/dobavit/", views.PCBCreateView.as_view(), name="pcb_create"),
    path("platy/<int:pk>/", views.PCBDetailView.as_view(), name="pcb_detail"),
    path("platy/<int:pk>/skachat/", views.pcb_download, name="pcb_download"),
    path("platy/<int:pk>/prosmotr/", views.PCBPreviewView.as_view(), name="pcb_preview"),
    path("platy/<int:pk>/plata.svg", views.pcb_svg, name="pcb_svg"),
    path("platy/fayl/<path:path>", views.pcb_file, name="pcb_file"),
    path("<slug:category_slug>/", views.ReceiverListView.as_view(), name="receiver_list"),
    path("<slug:category_slug>/<slug:slug>/", views.ReceiverDetailView.as_view(), name="receiver_detail"),
    path("<slug:category_slug>/<slug:slug>/redaktirovat/", views.ReceiverUpdateView.as_view(), name="receiver_edit"),
    path("<slug:category_slug>/<slug:slug>/instrukciya/", views.ReceiverManualView.as_view(), name="receiver_manual"),
    path("<slug:category_slug>/<slug:slug>/risunok/", views.ReceiverDrawingView.as_view(), name="receiver_drawing"),
]
