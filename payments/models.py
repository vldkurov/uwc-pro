from uuid import uuid4

from django.db import models


class Donor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"


class Donation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="donations")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    donated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Donation by {self.donor.first_name} {self.donor.last_name} - £{self.amount}"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    product_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    type = models.CharField(max_length=50, default="SERVICE")
    category = models.CharField(max_length=50, default="DONATIONS")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    plan_id = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    interval_unit = models.CharField(
        max_length=10,
        choices=[("WEEK", "Weekly"), ("MONTH", "Monthly"), ("YEAR", "Yearly")],
    )
    interval_count = models.IntegerField()
    currency = models.CharField(max_length=10, default="GBP")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.interval_unit})"


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    donor = models.ForeignKey(
        Donor, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="subscriptions"
    )
    subscription_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("ACTIVE", "Active"),
            ("CANCELLED", "Cancelled"),
            ("SUSPENDED", "Suspended"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Subscription {self.subscription_id} for {self.donor.email}"
