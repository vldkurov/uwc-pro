import re

from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from locations.models import Branch, Phone, Email, Person
from locations.validators import format_uk_phone_number


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["title_en", "title_uk", "address", "postcode", "url"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title_en"].label = "Branch Name (English)"
        self.fields["title_uk"].label = "Branch Name (Ukrainian)"
        self.fields["address"].label = "Branch Address"
        self.fields["postcode"].label = "Postal Code"
        self.fields["url"].label = "Website URL"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            FloatingField("title_en"),
            FloatingField("title_uk"),
            FloatingField("address"),
            FloatingField("postcode"),
            FloatingField("url"),
        )

    def clean_postcode(self):
        postcode = self.cleaned_data.get("postcode")
        if not postcode:
            return postcode
        postcode = postcode.strip().upper()
        uk_postcode_pattern = re.compile(
            r"^([A-Z]{1,2}[0-9]{1,2}[A-Z]?[ ]?[0-9][A-Z]{2}|GIR 0AA)$"
        )
        if not uk_postcode_pattern.match(postcode):
            raise ValidationError("Please enter a valid UK postcode.")
        if " " not in postcode:
            postcode = f"{postcode[:-3]} {postcode[-3:]}"
        return postcode

    def clean(self):
        cleaned_data = super().clean()
        for field in ["title_en", "title_uk", "address"]:
            value = cleaned_data.get(field, "")
            if value:
                cleaned_data[field] = " ".join(
                    word.capitalize() for word in value.strip().split()
                )
        return cleaned_data


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            "first_name_en",
            "last_name_en",
            "first_name_uk",
            "last_name_uk",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name_en"].label = "First Name (English)"
        self.fields["last_name_en"].label = "Last Name (English)"
        self.fields["first_name_uk"].label = "First Name (Ukrainian)"
        self.fields["last_name_uk"].label = "Last Name (Ukrainian)"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            FloatingField("first_name_en"),
            FloatingField("last_name_en"),
            FloatingField("first_name_uk"),
            FloatingField("last_name_uk"),
        )

    def clean(self):
        cleaned_data = super().clean()
        for field in ["first_name_en", "last_name_en", "first_name_uk", "last_name_uk"]:
            value = cleaned_data.get(field, "")
            if value:
                cleaned_data[field] = " ".join(
                    word.capitalize() for word in value.strip().split()
                )
        return cleaned_data


class PhoneForm(forms.ModelForm):
    class Meta:
        model = Phone
        fields = [
            "number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["number"].label = "Phone Number"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(FloatingField("number"))

    def clean_number(self):
        number = self.cleaned_data.get("number", "")
        if number:
            return format_uk_phone_number(number)
        return number


class EmailForm(forms.ModelForm):
    class Meta:
        model = Email
        fields = [
            "email",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].label = "Email Address"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(FloatingField("email"))

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip().lower()
        return email


PhoneFormSet = inlineformset_factory(
    Branch, Phone, form=PhoneForm, extra=1, can_delete=True
)

EmailFormSet = inlineformset_factory(
    Branch,
    Email,
    form=EmailForm,
    extra=1,
    can_delete=True,
)
