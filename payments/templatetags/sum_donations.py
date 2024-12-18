from django import template

register = template.Library()


@register.filter(name="sum_donations")
def sum_donations(donations):
    return sum(donation.amount for donation in donations)
