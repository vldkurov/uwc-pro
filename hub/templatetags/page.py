from django import template

register = template.Library()


@register.filter
def model_name(obj: object) -> str:
    meta = getattr(obj, "_meta", None)
    return meta.model_name if meta else None
