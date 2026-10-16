from decimal import Decimal

from django.conf import settings

from shop.models import Product

MAX_QUANTITY = 99


def max_quantity(product):
    return max(0, min(MAX_QUANTITY, product.stock))


class Cart:
    def __init__(self, request):
        self.session = request.session
        # Только читаем: сессию создаёт лишь первое изменение корзины, а не каждый просмотр страницы
        self.cart = dict(self.session.get(settings.CART_SESSION_KEY) or {})

    def add(self, product, quantity=1):
        """Добавляет товар, не превышая остаток. Возвращает итоговое количество в корзине."""
        product_id = str(product.pk)
        total = min(self.cart.get(product_id, 0) + quantity, max_quantity(product))
        if total > 0:
            self.cart[product_id] = total
            self.save()
        return total

    def set(self, product, quantity):
        product_id = str(product.pk)
        quantity = min(quantity, max_quantity(product))
        if quantity <= 0:
            self.cart.pop(product_id, None)
        else:
            self.cart[product_id] = quantity
        self.save()

    def remove(self, product):
        if self.cart.pop(str(product.pk), None) is not None:
            self.save()

    def clear(self):
        self.cart = {}
        self.save()

    def save(self):
        self.session[settings.CART_SESSION_KEY] = self.cart
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(pk__in=self.cart.keys(), is_active=True)
        product_map = {str(p.pk): p for p in products}
        for product_id, quantity in self.cart.items():
            product = product_map.get(product_id)
            if not product:
                continue
            yield {
                "product": product,
                "quantity": quantity,
                "price": product.price,
                "subtotal": product.price * quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    @property
    def total(self):
        return sum((item["subtotal"] for item in self), Decimal("0"))
