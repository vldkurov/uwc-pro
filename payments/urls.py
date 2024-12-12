from django.urls import path

from . import views

urlpatterns = [
    path("donate/", views.create_donation, name="create_donation"),
    path("success/", views.payment_success, name="payment_success"),
    path("cancel/", views.payment_cancel, name="payment_cancel"),
]
