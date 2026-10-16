from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from catalog.models import PCBFile, Receiver


@receiver(pre_delete, sender=PCBFile)
def remember_pcb_receivers(sender, instance, **kwargs):
    instance._receiver_ids = list(instance.receivers.values_list("pk", flat=True))


@receiver(post_delete, sender=PCBFile)
def deactivate_shop_products_without_boards(sender, instance, **kwargs):
    ids = getattr(instance, "_receiver_ids", [])
    for radio in Receiver.objects.filter(pk__in=ids):
        if radio.pcb_files.exists():
            continue
        radio.products.filter(is_active=True).update(is_active=False)
