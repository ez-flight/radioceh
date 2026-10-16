from django.conf import settings
from django.db import models
from django.urls import reverse

from catalog.models import PCBFile, Receiver


class Product(models.Model):
    class Kind(models.TextChoices):
        KIT = "kit", "Комплект модернизации"
        PCB = "pcb", "Печатная плата"
        FILEPACK = "filepack", "Пакет LAY-файлов"
        BOOK = "book", "Книга / сканы"

    title = models.CharField("Название", max_length=220)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices, default=Kind.KIT)
    description = models.TextField("Описание")
    price = models.DecimalField("Цена, ₽", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField("Остаток", default=10)
    is_active = models.BooleanField("В продаже", default=True)
    receiver = models.ForeignKey(
        Receiver,
        verbose_name="Приёмник",
        related_name="products",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    pcb_files = models.ManyToManyField(PCBFile, verbose_name="Файлы плат", blank=True, related_name="products")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("shop:product_detail", args=[self.slug])


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PROCESSING = "processing", "В работе"
        DONE = "done", "Выполнен"
        CANCELLED = "cancelled", "Отменён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    customer_name = models.CharField("Имя", max_length=160)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=40, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    total = models.DecimalField("Сумма, ₽", max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заказ №{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField("Количество", default=1)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity
