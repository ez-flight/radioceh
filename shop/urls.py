from django.urls import path

from shop import views

app_name = "shop"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("korzina/", views.cart_view, name="cart"),
    path("oformlenie/", views.checkout, name="checkout"),
    path("zakaz/<int:pk>/", views.order_success, name="order_success"),
    path("moi-zakazy/", views.my_orders, name="my_orders"),
    path("korzina/dobavit/<slug:slug>/", views.cart_add, name="cart_add"),
    path("korzina/ubrat/<slug:slug>/", views.cart_remove, name="cart_remove"),
    path("<slug:slug>/", views.ProductDetailView.as_view(), name="product_detail"),
]
