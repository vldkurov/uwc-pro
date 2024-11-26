from modeltranslation.translator import register, TranslationOptions

from .models import Page, Section, Text


@register(Page)
class PageTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(Section)
class SectionTranslationOptions(TranslationOptions):
    fields = ("title", "title_draft")


@register(Text)
class ContentTranslationOptions(TranslationOptions):
    fields = ("content", "content_draft", "is_update_pending", "is_update_confirmed")
