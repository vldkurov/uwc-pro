from django.shortcuts import render, redirect

from .forms import CustomDonationForm
from .utils import paypalrestsdk


def create_donation(request):
    if request.method == "POST":
        form = CustomDonationForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
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
                            "amount": {"total": str(amount), "currency": "GBP"},
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


def payment_success(request):
    """Handle a successful payment"""
    payment_id = request.GET.get("paymentId")
    payer_id = request.GET.get("PayerID")

    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        return render(request, "payments/success.html", {"details": payment.to_dict()})
    else:
        return render(request, "payments/error.html", {"error": payment.error})


def payment_cancel(request):
    """Handle a canceled payment"""
    return render(request, "payments/cancel.html")
