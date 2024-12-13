from django.urls import path

from . import views

urlpatterns = [
    # Single payment
    path("donate/", views.create_donation, name="create_donation"),
    # Endpoint for setting up subscription donations
    path("subscribe/", views.create_subscription, name="create_subscription"),
    # Webhook for handling PayPal events (e.g., subscription updates, payments)
    path("webhook/", views.paypal_webhook, name="paypal_webhook"),
    # Single payment: success and cancellation endpoints
    path("success/", views.payment_success, name="payment_success"),
    path("cancel/", views.payment_cancel, name="payment_cancel"),
    # Subscription: success and cancellation endpoints
    path(
        "subscription/success/", views.subscription_success, name="subscription_success"
    ),
    path("subscription/cancel/", views.subscription_cancel, name="subscription_cancel"),
]
