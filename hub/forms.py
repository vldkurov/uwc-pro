from django import forms
from django.forms import inlineformset_factory
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from .models import Section, Page


class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ["title_en", "title_uk"]
        labels = {
            "title_en": mark_safe(
                'Page Title <img src="/static/img/flags/gb.svg" alt="English" style="width: 30px; vertical-align: middle; margin-left: 6px;">'
            ),
            "title_uk": mark_safe(
                'Page Title <img src="/static/img/flags/ua.svg" alt="Ukrainian" style="width: 30px; vertical-align: middle; margin-left: 6px;">'
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        title_fields = [field for field in self.fields if field.startswith("title_")]
        is_any_title_filled = False

        for field in title_fields:
            if cleaned_data.get(field):
                is_any_title_filled = True
            else:
                self.add_error(field, _("This field is required."))
        if not is_any_title_filled:
            self.add_error(None, _("Title must be provided."))

        return cleaned_data


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["title_draft_en", "title_draft_uk"]
        widgets = {
            "title_draft_en": forms.TextInput(attrs={"placeholder": ""}),
            "title_draft_uk": forms.TextInput(attrs={"placeholder": ""}),
        }


SectionFormSet = inlineformset_factory(
    Page,
    Section,
    form=SectionForm,
    extra=0,
    can_delete=True,
)
