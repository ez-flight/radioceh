from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from shop.cart import MAX_QUANTITY, Cart, max_quantity
from shop.forms import CheckoutForm
from shop.models import Order, OrderItem, Product


class ProductListView(ListView):
    model = Product
    paginate_by = 12
    template_name = "shop/product_list.html"
    context_object_name = "products"

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related("receiver")
        kind = self.request.GET.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filters"] = self.request.GET
        ctx["kinds"] = Product.Kind.choices
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = "shop/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.select_related("receiver").prefetch_related(
            "pcb_files", "receiver__factories", "receiver__bands"
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_active:
            if self.object.receiver_id:
                return redirect(self.object.receiver.get_absolute_url())
            return redirect("shop:product_list")
        return self.render_to_response(self.get_context_data())


ORDERS_SESSION_KEY = "placed_orders"


def parse_quantity(raw):
    try:
        return min(max(1, int(raw)), MAX_QUANTITY)
    except (TypeError, ValueError):
        return 1


def safe_next(request, fallback):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


@require_POST
def cart_add(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if max_quantity(product) == 0:
        messages.warning(request, f"«{product.title}» сейчас нет в наличии.")
        return redirect(product.get_absolute_url())
    requested = parse_quantity(request.POST.get("quantity"))
    cart = Cart(request)
    before = cart.cart.get(str(product.pk), 0)
    total = cart.add(product, requested)
    if total < before + requested:
        messages.info(request, f"В корзине {total} шт. «{product.title}» — больше нет в наличии.")
    else:
        messages.success(request, f"«{product.title}» добавлен в корзину.")
    return redirect(safe_next(request, product.get_absolute_url()))


@require_POST
def cart_remove(request, slug):
    product = get_object_or_404(Product, slug=slug)
    Cart(request).remove(product)
    messages.info(request, f"«{product.title}» удалён из корзины.")
    return redirect("shop:cart")


def cart_view(request):
    return render(request, "shop/cart.html")


def checkout(request):
    cart = Cart(request)
    items = list(cart)
    if not items:
        messages.warning(request, "Корзина пуста.")
        return redirect("shop:product_list")

    user = request.user if request.user.is_authenticated else None
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = place_order(form, cart, user)
            except OutOfStock as exc:
                messages.warning(request, str(exc))
                return redirect("shop:cart")
            cart.clear()
            placed = request.session.get(ORDERS_SESSION_KEY, [])
            request.session[ORDERS_SESSION_KEY] = (placed + [order.pk])[-20:]
            messages.success(request, f"Заявка №{order.pk} принята. Мы свяжемся с вами по email.")
            return redirect("shop:order_success", pk=order.pk)
    else:
        form = CheckoutForm(initial={
            "customer_name": (user.get_full_name() or user.username) if user else "",
            "email": user.email if user else "",
        })

    return render(request, "shop/checkout.html", {"items": items, "form": form})


class OutOfStock(Exception):
    pass


def place_order(form, cart, user):
    """Создаёт заказ по актуальным ценам и списывает остаток; товары блокируются до конца транзакции."""
    with transaction.atomic():
        wanted = dict(cart.cart)
        products = {
            str(p.pk): p
            for p in Product.objects.select_for_update().filter(pk__in=wanted.keys(), is_active=True)
        }
        lines = []
        for product_id, quantity in wanted.items():
            product = products.get(product_id)
            if product is None:
                continue
            if quantity > product.stock:
                raise OutOfStock(f"«{product.title}»: в наличии {product.stock} шт. Уменьшите количество в корзине.")
            lines.append((product, quantity))
        if not lines:
            raise OutOfStock("Товары из корзины больше не продаются.")

        order = form.save(commit=False)
        order.user = user
        order.total = sum((p.price * q for p, q in lines), Decimal("0"))
        order.save()
        for product, quantity in lines:
            OrderItem.objects.create(order=order, product=product, quantity=quantity, price=product.price)
            product.stock -= quantity
            product.save(update_fields=["stock"])
        return order


def can_view_order(request, order):
    user = request.user
    if user.is_authenticated and (user.is_staff or order.user_id == user.pk):
        return True
    return order.pk in request.session.get(ORDERS_SESSION_KEY, [])


def order_success(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not can_view_order(request, order):
        raise Http404("Заказ не найден.")
    return render(request, "shop/order_success.html", {"order": order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items__product")
    return render(request, "shop/order_list.html", {"orders": orders})
