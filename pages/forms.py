from django import forms
from django.utils.translation import gettext as _


class SearchForm(forms.Form):
    query = forms.CharField(label=_("Search"), required=False)
