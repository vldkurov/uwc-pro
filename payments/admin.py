from django.contrib import admin

from .models import Donor, Donation


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "created_at")
    search_fields = ("first_name", "last_name", "email")


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("donor", "amount", "transaction_id", "donated_at")
    search_fields = ("transaction_id",)
    list_filter = ("donated_at",)
