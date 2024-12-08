import re

from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, Select
from django.forms.widgets import Textarea

from locations.models import Branch, Phone, Email, Person
from locations.validators import format_uk_phone_number


class BranchForm(forms.ModelForm):
    """
    BranchForm is a Django ModelForm for managing the creation and validation of branch
    data in a web application. It specializes in organizing form fields and ensuring data
    integrity according to specific validation rules and UI enhancements, particularly for
    branch titles, addresses, and postcodes.

    This class configures the form layout and widgets using crispy-forms and customizes the
    field labels to improve user experience. It contains methods to clean and validate
    individual form fields like postcodes and applies transformations to ensure data is
    formatted correctly before processing.

    :ivar helper: A FormHelper instance used to customize the layout and appearance of the form.
    :type helper: FormHelper
    """

    class Meta:
        model = Branch
        fields = [
            "title_en",
            "title_uk",
            "address",
            "postcode",
            "url",
            "parish_priest",
            "branch_chair",
            "branch_secretary",
            "other_details",
        ]
        widgets = {
            "parish_priest": Select(attrs={"class": "form-select py-3"}),
            "branch_chair": Select(attrs={"class": "form-select py-3"}),
            "branch_secretary": Select(attrs={"class": "form-select py-3"}),
            "other_details": Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title_en"].label = "Branch Name (English)"
        self.fields["title_uk"].label = "Branch Name (Ukrainian)"
        self.fields["address"].label = "Branch Address"
        self.fields["postcode"].label = "Postal Code"
        self.fields["url"].label = "Website URL"
        self.fields["other_details"].label = "Other Details"

        self.fields["parish_priest"].label = "Parish Priest"
        self.fields["parish_priest"].queryset = Person.objects.all()
        self.fields["branch_chair"].label = "Branch Chair"
        self.fields["branch_chair"].queryset = Person.objects.all()
        self.fields["branch_secretary"].label = "Branch Secretary"
        self.fields["branch_secretary"].queryset = Person.objects.all()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            FloatingField("title_en"),
            FloatingField("title_uk"),
            FloatingField("address"),
            FloatingField("postcode"),
            FloatingField("url"),
            FloatingField("other_details"),
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

    def clean_address(self):
        address_value = self.cleaned_data.get("address", "")
        if not address_value:
            return address_value
        words = address_value.split()
        return " ".join(
            word.capitalize() if not word.startswith("'") else word for word in words
        )

    def clean(self):
        cleaned_data = super().clean()
        for field in ["title_en", "title_uk"]:
            value = cleaned_data.get(field, "")
            if value:
                cleaned_data[field] = value.strip().title()
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
