import re

from django import template

register = template.Library()


@register.filter(name="highlight_query")
def highlight_query(value, query):

    if not value or not query:
        return value

    words = query.split()
    pattern = "|".join(re.escape(word) for word in words)

    highlighted = re.sub(
        pattern,
        lambda match: f'<span class="bg-warning text-dark">{match.group(0)}</span>',
        str(value),
        flags=re.IGNORECASE,
    )
    return highlighted
