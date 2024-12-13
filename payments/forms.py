from django import forms
from django.utils.translation import gettext as _


class CustomDonationForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label=_("or enter your own amount (£):"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Enter amount"}
        ),
    )
