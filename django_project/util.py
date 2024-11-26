import string
from random import choice

from django.utils.text import slugify


def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    return "".join(choice(chars) for _ in range(size))


def unique_slug_generator(instance, new_slug=None, suffix_length=4):
    if new_slug is not None:
        slug = new_slug
    else:
        if not instance.title:
            raise ValueError("Instance must have a 'title' before generating a slug.")
        slug = slugify(instance.title)
    Klass = instance.__class__
    max_length = Klass._meta.get_field("slug").max_length
    slug = slug[:max_length]
    qs_exists = Klass.objects.filter(slug=slug).exists()

    if qs_exists:
        new_slug = f"{slug[:max_length - suffix_length - 1]}-{random_string_generator(size=suffix_length)}"
        return unique_slug_generator(
            instance, new_slug=new_slug, suffix_length=suffix_length
        )
    return slug
