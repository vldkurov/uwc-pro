import logging
import os
import sys

import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uwc_pro.settings")
django.setup()

import paypalrestsdk
from django.conf import settings

paypalrestsdk.configure(
    {
        "mode": settings.PAYPAL_MODE,
        "client_id": settings.PAYPAL_CLIENT_ID,
        "client_secret": settings.PAYPAL_CLIENT_SECRET,
    }
)


import requests
from django.conf import settings
from payments.models import Product, Plan

logger = logging.getLogger(__name__)


def get_access_token():
    url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET)
    headers = {"Accept": "application/json", "Accept-Language": "en_GB"}
    data = {"grant_type": "client_credentials"}

    response = requests.post(url, headers=headers, data=data, auth=auth)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        return None


def create_product(name, product_type="SERVICE", category="CHARITY"):
    access_token = get_access_token()
    if not access_token:
        return None

    url = "https://api-m.sandbox.paypal.com/v1/catalogs/products"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {
        "name": name,
        "type": product_type,
        "category": category,
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        product_data = response.json()
        product, created = Product.objects.get_or_create(
            product_id=product_data["id"],
            defaults={
                "name": name,
                "type": product_type,
                "category": category,
            },
        )
        return product
    else:
        return None


def create_billing_plan(
    product, name, amount, interval_unit, interval_count, currency="GBP"
):
    access_token = get_access_token()
    if not access_token:
        return None

    url = "https://api-m.sandbox.paypal.com/v1/billing/plans"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {
        "product_id": product.product_id,
        "name": name,
        "description": f"{name} Plan",
        "status": "ACTIVE",
        "billing_cycles": [
            {
                "frequency": {
                    "interval_unit": interval_unit,
                    "interval_count": interval_count,
                },
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": str(amount),
                        "currency_code": currency,
                    }
                },
            }
        ],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee": {"value": "0", "currency_code": currency},
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3,
        },
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        plan_data = response.json()
        plan, created = Plan.objects.get_or_create(
            plan_id=plan_data["id"],
            defaults={
                "product": product,
                "name": name,
                "amount": amount,
                "interval_unit": interval_unit,
                "interval_count": interval_count,
                "currency": currency,
            },
        )
        return plan
    else:
        return None


def create_subscription(plan, donor, return_url, cancel_url):
    access_token = get_access_token()
    if not access_token:
        raise ValueError("Failed to fetch PayPal access token.")

    url = "https://api-m.sandbox.paypal.com/v1/billing/subscriptions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {
        "plan_id": plan.plan_id,
        "subscriber": {
            "name": {"given_name": donor.first_name, "surname": donor.last_name},
            "email_address": donor.email,
        },
        "application_context": {
            "brand_name": "UWC",
            "locale": "en-GB",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    else:
        response.raise_for_status()
