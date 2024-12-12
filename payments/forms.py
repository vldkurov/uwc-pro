from django import forms


class CustomDonationForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Or enter your own amount:",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Enter amount"}
        ),
    )
