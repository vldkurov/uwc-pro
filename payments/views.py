import json
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .forms import CustomDonationForm
from .models import Donor, Donation, Subscription, Plan
from .utils import (
    paypalrestsdk,
    create_product,
    create_billing_plan,
    create_subscription as create_subscription_util,
    get_access_token,
)

logger = logging.getLogger(__name__)


def create_donation(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        form = CustomDonationForm(request.POST) if not amount else None

        if amount:
            print("amount (raw):", amount)
            try:
                formatted_amount = Decimal(amount.replace("£", "").strip())
            except (ValueError, InvalidOperation):
                return render(
                    request,
                    "payments/error.html",
                    {"error": "Invalid donation amount format."},
                )

        elif form and form.is_valid():
            formatted_amount = form.cleaned_data["amount"]

        else:
            return render(request, "payments/donate.html", {"form": form})

        return_url = request.build_absolute_uri("/payments/success/")
        cancel_url = request.build_absolute_uri("/payments/cancel/")

        payment = paypalrestsdk.Payment(
            {
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
                "transactions": [
                    {
                        "amount": {
                            "total": f"{formatted_amount:.2f}",
                            "currency": "GBP",
                        },
                        "description": "Donation for the non-profit organisation",
                    }
                ],
            }
        )

        if payment.create():
            for link in payment.links:
                if link.rel == "approval_url":
                    return redirect(link.href)
        else:
            return render(request, "payments/error.html", {"error": payment.error})

    else:
        form = CustomDonationForm()
        return render(request, "payments/donate.html", {"form": form})


def create_subscription(request):
    if request.method == "POST":
        try:
            amount = request.POST.get("amount")
            interval_unit = request.POST.get("interval", "MONTH")

            donor, _ = Donor.objects.get_or_create(
                email="sb-43hker34651253@personal.example.com",
                defaults={"first_name": "John", "last_name": "Doe"},
            )

            product = create_product(
                name="Recurring Donation", product_type="SERVICE", category="CHARITY"
            )
            if not product:
                return JsonResponse({"error": "Failed to create product"}, status=500)

            plan = create_billing_plan(
                product=product,
                name="Recurring Donation",
                amount=amount,
                interval_unit=interval_unit,
                interval_count=1,
                currency="GBP",
            )
            if not plan:
                return JsonResponse({"error": "Failed to create plan"}, status=500)

            subscription_response = create_subscription_util(
                plan=plan,
                donor=donor,
                return_url=request.build_absolute_uri(
                    "/payments/subscription/success/"
                ),
                cancel_url=request.build_absolute_uri("/payments/subscription/cancel/"),
            )

            if subscription_response:
                approval_url = next(
                    (
                        link["href"]
                        for link in subscription_response.get("links", [])
                        if link["rel"] == "approve"
                    ),
                    None,
                )
                if approval_url:
                    return redirect(approval_url)

            return JsonResponse({"error": "Failed to create subscription"}, status=500)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return render(request, "payments/donate.html")


def payment_success(request):
    """Handle a successful payment"""
    payment_id = request.GET.get("paymentId")
    payer_id = request.GET.get("PayerID")

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        if payment.execute({"payer_id": payer_id}):
            payer_info = payment.payer.payer_info
            transaction = payment.transactions[0]

            donor, created = Donor.objects.get_or_create(
                email=payer_info.email,
                defaults={
                    "first_name": payer_info.first_name,
                    "last_name": payer_info.last_name,
                },
            )

            donation = Donation.objects.create(
                donor=donor,
                amount=transaction.amount.total,
                transaction_id=payment.id,
            )

            send_mail(
                subject="Thank you for your donation!",
                message=f"Dear {donor.first_name},\n\n"
                f"Thank you for your generous donation of £{donation.amount}.\n\n"
                f"Transaction ID: {donation.transaction_id}\n\n"
                f"We deeply appreciate your support!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[donor.email],
            )

            return render(request, "payments/success.html", {"donation": donation})
        else:
            return render(request, "payments/error.html", {"error": payment.error})
    except Exception as e:
        return render(request, "payments/error.html", {"error": str(e)})


def payment_cancel(request):
    """Handle a canceled payment"""
    return render(request, "payments/cancel.html")


@csrf_exempt
def paypal_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            event_type = data.get("event_type")
            resource = data.get("resource")

            if event_type == "BILLING.SUBSCRIPTION.CREATED":
                subscription_id = resource.get("id")
                plan_id = resource.get("plan_id")
                donor_email = resource.get("subscriber", {}).get("email_address")

                plan = Plan.objects.filter(plan_id=plan_id).first()
                donor, _ = Donor.objects.get_or_create(email=donor_email)

                Subscription.objects.create(
                    subscription_id=subscription_id,
                    plan=plan,
                    donor=donor,
                    status="ACTIVE",
                )
                return JsonResponse({"status": "subscription_created"})

            elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
                subscription_id = resource.get("id")
                subscription = Subscription.objects.filter(
                    subscription_id=subscription_id
                ).first()
                if subscription:
                    subscription.status = "CANCELLED"
                    subscription.save()
                return JsonResponse({"status": "subscription_cancelled"})

            elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
                subscription_id = resource.get("id")
                subscription = Subscription.objects.filter(
                    subscription_id=subscription_id
                ).first()
                if subscription:
                    subscription.status = "SUSPENDED"
                    subscription.save()
                return JsonResponse({"status": "subscription_suspended"})

            elif event_type == "PAYMENT.SALE.COMPLETED":
                subscription_id = resource.get("billing_agreement_id")
                payment_amount = resource.get("amount", {}).get("total")
                currency = resource.get("amount", {}).get("currency")

                return JsonResponse({"status": "payment_completed"})

            return JsonResponse({"status": "event_ignored"})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return HttpResponse(status=405)


def get_subscription_details(subscription_id):
    access_token = get_access_token()
    url = f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def subscription_success(request):
    subscription_id = request.GET.get("subscription_id")
    try:
        if subscription_id:
            response = get_subscription_details(subscription_id)
            if response and response.get("status") == "ACTIVE":
                plan_id = response.get("plan_id")
                subscriber_email = response.get("subscriber", {}).get("email_address")

                plan = Plan.objects.filter(plan_id=plan_id).first()
                donor, created = Donor.objects.get_or_create(
                    email=subscriber_email,
                    defaults={"first_name": "Unknown", "last_name": "Unknown"},
                )

                subscription, created = Subscription.objects.update_or_create(
                    subscription_id=subscription_id,
                    defaults={
                        "plan": plan,
                        "donor": donor,
                        "status": response.get("status"),
                        "created_at": response.get("start_time"),
                        "updated_at": response.get("update_time"),
                    },
                )

                send_mail(
                    subject="Thank you for subscribing!",
                    message=(
                        f"Dear {subscription.donor.first_name},\n\n"
                        f'Thank you for joining us and subscribing to the "{subscription.plan.name}" plan!\n\n'
                        f"Your subscription details are as follows:\n"
                        f"- Subscription ID: {subscription.subscription_id}\n"
                        f"- Plan: {subscription.plan.name}\n"
                        f"- Amount: £{subscription.plan.amount} {subscription.plan.currency}\n"
                        f"- Billing Frequency: Every {subscription.plan.interval_count} {subscription.plan.interval_unit.lower()}(s)\n\n"
                        f"Your support means so much to us and helps us continue making a difference. "
                        f"If you have any questions or need assistance, feel free to reach out.\n\n"
                        f"Thank you for being a part of our community!\n\n"
                        f"Warm regards,\n"
                        f"The Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscription.donor.email],
                )

                return render(
                    request,
                    "payments/subscription_success.html",
                    {
                        "subscription": subscription,
                        "status": response.get("status"),
                    },
                )

            return render(
                request,
                "payments/subscription_error.html",
                {
                    "error": "Subscription details not found.",
                },
            )
    except Exception as e:
        return render(request, "payments/subscription_error.html", {"error": str(e)})


def subscription_cancel(request):
    """Handle a canceled subscription"""
    return render(request, "payments/subscription_cancel.html")
