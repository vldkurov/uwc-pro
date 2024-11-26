from modeltranslation.translator import register, TranslationOptions

from .models import Division, Branch, Person


@register(Division)
class DivisionTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(Branch)
class BranchTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(Person)
class PersonTranslationOptions(TranslationOptions):
    fields = (
        "first_name",
        "last_name",
    )
