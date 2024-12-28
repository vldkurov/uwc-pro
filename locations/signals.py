from django.db.models.signals import pre_save
from django.dispatch import receiver

from django_project.geocode import geocode
from django_project.util import unique_slug_generator
from .models import Division, Branch


@receiver(pre_save, sender=Division)
def division_pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.title_en and not instance.title_uk:
        return

    if not instance.slug:
        instance.slug = unique_slug_generator(instance)


def update_geocoding(instance):
    result = geocode(instance.address, instance.postcode)
    if result:
        formatted_address, lat, lng, place_id = result
        instance.formatted_address = formatted_address
        instance.lat = lat
        instance.lng = lng
        instance.place_id = place_id


@receiver(pre_save, sender=Branch)
def branch_pre_save_receiver(sender, instance, *args, **kwargs):
    if not instance.slug:
        instance.slug = unique_slug_generator(instance)

    if instance.pk:
        try:
            current_instance = Branch.objects.get(pk=instance.pk)
            address_changed = current_instance.address != instance.address
            postcode_changed = current_instance.postcode != instance.postcode

            if not instance.place_id or address_changed or postcode_changed:
                update_geocoding(instance)
        except Branch.DoesNotExist:
            update_geocoding(instance)
    else:
        if not instance.place_id:
            update_geocoding(instance)
