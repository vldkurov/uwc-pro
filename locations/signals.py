from django.db.models.signals import pre_save
from django.dispatch import receiver

from django_project.util import unique_slug_generator
from .models import Division, Branch


@receiver(pre_save, sender=Division)
def division_pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.slug:
        instance.slug = unique_slug_generator(instance)


@receiver(pre_save, sender=Branch)
def branch_pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.slug:
        instance.slug = unique_slug_generator(instance)
