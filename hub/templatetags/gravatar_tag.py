import hashlib
from urllib.parse import urlencode

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def gravatar_url(email, size=40):
    default = "identicon"
    email_encoded = email.lower().encode("utf-8")
    email_hash = hashlib.md5(email_encoded).hexdigest()
    params = urlencode({"d": default, "s": str(size)})
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"


@register.filter
def gravatar(email, size=40):
    url = gravatar_url(email, size)
    return mark_safe(
        f'<img src="{url}" alt="Gravatar" class="rounded-circle" width="{size}" height="{size}">'
    )


@register.filter
def gravatar_with_type(email, args="40,identicon"):
    size, default_type = args.split(",")
    email_encoded = email.lower().encode("utf-8")
    email_hash = hashlib.md5(email_encoded).hexdigest()
    params = urlencode({"d": default_type.strip(), "s": size.strip()})
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"
