from django.contrib import admin

from .models import Page, Section


class SectionInline(admin.StackedInline):
    model = Section
    extra = 1
    fields = ["title_draft", "status", "order"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "created"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [SectionInline]
