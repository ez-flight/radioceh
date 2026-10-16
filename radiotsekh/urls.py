from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

from catalog.views import HomeView, about, redirect_old_library
from radiotsekh.views import RegisterView

admin.site.site_header = "Радиоцех"
admin.site.site_title = "Радиоцех"
admin.site.index_title = "Каталог и магазин"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeView.as_view(), name="home"),
    path("o-proekte/", about, name="about"),
    path("katalog/", include("catalog.urls")),
    path("biblioteka/", RedirectView.as_view(pattern_name="catalog:catalog_index", permanent=False)),
    path("biblioteka/<path:rest>", redirect_old_library),
    path("magazin/", include("shop.urls")),
    path("vhod/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("vyhod/", auth_views.LogoutView.as_view(), name="logout"),
    path("registraciya/", RegisterView.as_view(), name="register"),
]

# Публичные загрузки (фото, обложки, сканы). Файлы плат лежат в PRIVATE_MEDIA_ROOT и сюда не попадают.
# nginx стоит перед сайтом, но к /home у него нет доступа (и не нужен: рядом лежат private/ и .env),
# поэтому публичную media/ отдаёт Django. При большой нагрузке — вынести media/ в каталог, доступный nginx.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
