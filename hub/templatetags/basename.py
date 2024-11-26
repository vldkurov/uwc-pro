import os

from django import template
from django.core.files.base import File

register = template.Library()


@register.filter
def basename(value):
    if isinstance(value, File):
        value = value.name
    return os.path.basename(value)
