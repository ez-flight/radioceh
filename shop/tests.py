from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from shop.models import Order, Product


class ShopTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="Плата УНЧ", slug="plata-unch", description="—", price=Decimal("1500.00"), stock=3
        )
        self.add_url = reverse("shop:cart_add", args=[self.product.slug])
        self.checkout_url = reverse("shop:checkout")

    def order_payload(self, **extra):
        data = {"customer_name": "Пётр", "email": "petr@example.com", "phone": "+7 900 000-00-00", "comment": ""}
        data.update(extra)
        return data

    def cart(self):
        return self.client.session.get("cart", {})

    def test_browsing_does_not_create_sessions(self):
        self.client.get(reverse("home"))
        self.client.get(reverse("shop:product_list"))
        self.assertEqual(Session.objects.count(), 0)

    def test_bad_quantity_does_not_crash(self):
        response = self.client.post(self.add_url, {"quantity": "abc"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.cart(), {str(self.product.pk): 1})

    def test_quantity_is_capped_by_stock(self):
        self.client.post(self.add_url, {"quantity": "1000000000000"})
        self.assertEqual(self.cart(), {str(self.product.pk): 3})

    def test_out_of_stock_product_is_not_added(self):
        self.product.stock = 0
        self.product.save()
        self.client.post(self.add_url, {"quantity": 1})
        self.assertEqual(self.cart(), {})

    def test_next_redirect_stays_on_site(self):
        evil = self.client.post(self.add_url, {"next": "https://evil.example/phish"})
        self.assertEqual(evil["Location"], self.product.get_absolute_url())
        local = self.client.post(self.add_url, {"next": "/magazin/korzina/"})
        self.assertEqual(local["Location"], "/magazin/korzina/")

    def test_checkout_validates_fields(self):
        self.client.post(self.add_url, {"quantity": 1})
        response = self.client.post(self.checkout_url, self.order_payload(customer_name="  ", email="не-почта"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(response.context["form"].has_error("customer_name"))
        self.assertTrue(response.context["form"].has_error("email"))

    def test_checkout_creates_order_and_reduces_stock(self):
        self.client.post(self.add_url, {"quantity": 2})
        response = self.client.post(self.checkout_url, self.order_payload())
        order = Order.objects.get()
        self.assertRedirects(response, reverse("shop:order_success", args=[order.pk]))
        self.assertEqual(order.total, Decimal("3000.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.cart(), {})

    def test_checkout_refuses_when_stock_ran_out(self):
        self.client.post(self.add_url, {"quantity": 3})
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        response = self.client.post(self.checkout_url, self.order_payload())
        self.assertRedirects(response, reverse("shop:cart"), fetch_redirect_response=False)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_page_visible_only_to_owner_session_or_staff(self):
        self.client.post(self.add_url, {"quantity": 1})
        self.client.post(self.checkout_url, self.order_payload())
        order = Order.objects.get()
        url = reverse("shop:order_success", args=[order.pk])
        self.assertContains(self.client.get(url), "petr@example.com")

        stranger = self.client_class()
        self.assertEqual(stranger.get(url).status_code, 404)

        User.objects.create_user("staff", "s@example.com", "staff", is_staff=True)
        stranger.login(username="staff", password="staff")
        self.assertEqual(stranger.get(url).status_code, 200)
