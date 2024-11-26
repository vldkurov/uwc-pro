from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Section, Content


@receiver(pre_delete, sender=Section)
def delete_related_content(sender, instance, **kwargs):
    Content.objects.filter(section=instance).delete()


@receiver(pre_delete, sender=Content)
def delete_related_item(sender, instance, **kwargs):
    if instance.item:
        instance.item.delete()
