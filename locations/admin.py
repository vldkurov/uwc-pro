from django.contrib import admin

from .models import Division, Person, Phone, Email, Branch


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)
    exclude = ("slug", "created_by", "updated_by", "order")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name")
    search_fields = ("first_name", "last_name")


@admin.register(Phone)
class PhoneAdmin(admin.ModelAdmin):
    list_display = ("number", "location")
    search_fields = ("number",)


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ("email", "location")
    search_fields = ("email",)


class PhoneInline(admin.TabularInline):
    model = Phone
    extra = 1


class EmailInline(admin.TabularInline):
    model = Email
    extra = 1


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("title", "division", "branch_chair", "parish_priest")
    search_fields = ("title", "address", "postcode")
    list_filter = ("division",)
    inlines = [PhoneInline, EmailInline]
    exclude = ("slug",)
    autocomplete_fields = ("branch_chair", "parish_priest")
