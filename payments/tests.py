import json
import logging
import uuid
from unittest.mock import patch, MagicMock, Mock

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse

from payments.forms import CustomDonationForm
from payments.models import Donor, Donation, Product, Plan, Subscription
from payments.views import get_subscription_details

User = get_user_model()


class CreateDonationViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Setup test data that will be available for all test methods.
        """
        cls.client = Client()
        cls.url = reverse("create_donation")
        cls.success_url = reverse("payment_success")
        cls.cancel_url = reverse("payment_cancel")

    def setUp(self):
        # Configure logger to suppress critical logs during tests
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    def test_get_request_renders_donation_form(self):
        """
        Test GET request renders the donation form.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/donate.html")
        self.assertIsInstance(response.context["form"], CustomDonationForm)

    @patch("payments.views.paypalrestsdk.Payment")
    def test_valid_post_request_creates_payment(self, mock_payment):
        """
        Test POST request with valid data creates PayPal payment and redirects.
        """
        # Mock PayPal payment creation
        mock_payment_instance = MagicMock()
        mock_payment_instance.create.return_value = True
        mock_payment_instance.links = [
            MagicMock(rel="approval_url", href="https://www.paypal.com/approval-url")
        ]
        mock_payment.return_value = mock_payment_instance

        response = self.client.post(self.url, {"amount": "10.00"})

        # Assert the redirect to PayPal approval URL
        self.assertRedirects(
            response,
            "https://www.paypal.com/approval-url",
            fetch_redirect_response=False,
        )

    @patch("payments.views.paypalrestsdk.Payment")
    def test_invalid_post_request_returns_error(self, mock_payment):
        """
        Test POST request with invalid data shows an error message.
        """
        # Mock failed PayPal payment creation
        mock_payment_instance = MagicMock()
        mock_payment_instance.create.return_value = False
        mock_payment_instance.error = "Invalid request"
        mock_payment.return_value = mock_payment_instance

        response = self.client.post(self.url, {"amount": "10.00"})

        # Assert the error page is displayed
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "Invalid request")

    def test_invalid_amount_format_shows_error(self):
        """
        Test POST request with invalid amount format returns error.
        """
        response = self.client.post(self.url, {"amount": "invalid_amount"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "Invalid donation amount format.")

    def test_blank_amount_shows_form(self):
        """
        Test POST request with blank amount re-renders the form.
        """
        response = self.client.post(self.url, {"amount": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/donate.html")
        self.assertIsInstance(response.context["form"], CustomDonationForm)


class CreateSubscriptionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("create_subscription")  # URL for the subscription view
        cls.donor_email = "sb-43hker34651253@personal.example.com"

    def setUp(self):
        """Set up common data for each test"""
        self.data = {
            "amount": "10.00",
            "interval": "MONTH",
        }

        # Configure logger to suppress critical logs during tests
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    @patch("payments.views.create_product")
    @patch("payments.views.create_billing_plan")
    @patch("payments.views.create_subscription_util")
    def test_valid_post_request_creates_subscription(
        self,
        mock_create_subscription_util,
        mock_create_billing_plan,
        mock_create_product,
    ):
        """
        Test valid POST request creates a subscription and redirects to approval URL.
        """
        # Mock dependencies
        mock_create_product.return_value = {"id": "product_123"}
        mock_create_billing_plan.return_value = {"id": "plan_123"}
        mock_create_subscription_util.return_value = {
            "links": [{"rel": "approve", "href": "https://www.paypal.com/approval-url"}]
        }

        # Send POST request
        response = self.client.post(self.url, self.data)

        # Assertions
        mock_create_product.assert_called_once_with(
            name="Recurring Donation", product_type="SERVICE", category="CHARITY"
        )
        mock_create_billing_plan.assert_called_once_with(
            product={"id": "product_123"},
            name="Recurring Donation",
            amount=self.data["amount"],
            interval_unit=self.data["interval"],
            interval_count=1,
            currency="GBP",
        )
        mock_create_subscription_util.assert_called_once()

        # Assert redirect to approval URL
        self.assertRedirects(
            response,
            "https://www.paypal.com/approval-url",
            fetch_redirect_response=False,
        )

    @patch("payments.views.create_product")
    def test_product_creation_failure_returns_error(self, mock_create_product):
        """
        Test if product creation failure returns 500 and error messages.
        """
        mock_create_product.return_value = None  # Simulate failure

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(response.content, {"error": "Failed to create product"})

    @patch("payments.views.create_product")
    @patch("payments.views.create_billing_plan")
    def test_plan_creation_failure_returns_error(
        self, mock_create_billing_plan, mock_create_product
    ):
        """
        Test if plan creation failure returns 500 and error message.
        """
        mock_create_product.return_value = {"id": "product_123"}
        mock_create_billing_plan.return_value = None  # Simulate failure

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(response.content, {"error": "Failed to create plan"})

    @patch("payments.views.create_product")
    @patch("payments.views.create_billing_plan")
    @patch("payments.views.create_subscription_util")
    def test_subscription_creation_failure_returns_error(
        self,
        mock_create_subscription_util,
        mock_create_billing_plan,
        mock_create_product,
    ):
        """
        Test if subscription creation failure returns 500 and error message.
        """
        # Mock valid product and plan
        mock_create_product.return_value = {"id": "product_123"}
        mock_create_billing_plan.return_value = {"id": "plan_123"}
        mock_create_subscription_util.return_value = None  # Simulate failure

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(
            response.content, {"error": "Failed to create subscription"}
        )

    def test_get_request_renders_donation_form(self):
        """
        Test GET request renders the donation form template.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/donate.html")


class PaymentSuccessViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("payment_success")
        cls.valid_payment_id = "PAY-12345"
        cls.valid_payer_id = "PAYER-67890"
        cls.donor_email = "john.doe@example.com"

    def setUp(self):
        """Setup common GET parameters."""
        self.query_params = {
            "paymentId": self.valid_payment_id,
            "PayerID": self.valid_payer_id,
        }

        # Configure logger to suppress critical logs during tests
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    @patch("payments.views.paypalrestsdk.Payment.find")
    @patch("payments.views.send_mail")
    def test_successful_payment_creates_donation(
        self, mock_send_mail, mock_find_payment
    ):
        """
        Test successful payment creates a donation and sends confirmation email.
        """
        # Mock PayPal Payment
        mock_payment = MagicMock()
        mock_payment.execute.return_value = True
        mock_payment.payer.payer_info = MagicMock(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )
        mock_payment.transactions = [MagicMock(amount=MagicMock(total="10.00"))]
        mock_payment.id = self.valid_payment_id
        mock_find_payment.return_value = mock_payment

        # Perform GET request
        response = self.client.get(self.url, self.query_params)

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/success.html")

        # Verify Donor creation
        self.assertEqual(Donor.objects.count(), 1)
        donor = Donor.objects.first()
        self.assertEqual(donor.email, self.donor_email)

        # Verify Donation creation
        self.assertEqual(Donation.objects.count(), 1)
        donation = Donation.objects.first()
        self.assertEqual(float(donation.amount), 10.00)
        self.assertEqual(donation.transaction_id, self.valid_payment_id)

        # Dynamic email sender
        expected_from_email = settings.DEFAULT_FROM_EMAIL

        # Verify email sent
        mock_send_mail.assert_called_once_with(
            subject="Thank you for your donation!",
            message=(
                f"Dear {donor.first_name},\n\n"
                f"Thank you for your generous donation of £{donation.amount}.\n\n"
                f"Transaction ID: {donation.transaction_id}\n\n"
                f"We deeply appreciate your support!"
            ),
            from_email=expected_from_email,
            recipient_list=[self.donor_email],
        )

    @patch("payments.views.paypalrestsdk.Payment.find")
    def test_payment_execution_failure_returns_error(self, mock_find_payment):
        """
        Test that payment execution failure renders error page.
        """
        # Mock Payment execution failure
        mock_payment = MagicMock()
        mock_payment.execute.return_value = False
        mock_payment.error = "Payment execution failed."
        mock_find_payment.return_value = mock_payment

        # Perform GET request
        response = self.client.get(self.url, self.query_params)

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "Payment execution failed.")

        # Verify no donor or donation is created
        self.assertEqual(Donor.objects.count(), 0)
        self.assertEqual(Donation.objects.count(), 0)

    @patch("payments.views.paypalrestsdk.Payment.find")
    def test_invalid_payment_id_raises_error(self, mock_find_payment):
        """
        Test invalid payment ID raises an error and renders error page.
        """
        # Mock payment not found
        mock_find_payment.side_effect = Exception("Invalid Payment ID")

        # Perform GET request
        response = self.client.get(self.url, self.query_params)

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "Invalid Payment ID")

        # Verify no donor or donation is created
        self.assertEqual(Donor.objects.count(), 0)
        self.assertEqual(Donation.objects.count(), 0)

    def test_missing_payment_id_or_payer_id(self):
        """
        Test that missing paymentId or PayerID renders error page.
        """
        # Missing paymentId
        response = self.client.get(self.url, {"PayerID": self.valid_payer_id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "error")

        # Missing PayerID
        response = self.client.get(self.url, {"paymentId": self.valid_payment_id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "error")

        # Missing both
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/error.html")
        self.assertContains(response, "error")


class PaymentCancelViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.url = reverse("payment_cancel")  # URL for the cancel view

    def setUp(self):
        """Setup logger to suppress logs during tests."""
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    def test_cancel_page_renders_correct_template(self):
        """
        Verify the cancel page renders the correct template.
        """
        response = self.client.get(self.url)

        # Check HTTP response status
        self.assertEqual(response.status_code, 200)

        # Assert the correct template is used
        self.assertTemplateUsed(response, "payments/cancel.html")

    def test_cancel_page_contains_message(self):
        """
        Verify the cancel page contains an appropriate message.
        """
        response = self.client.get(self.url)

        # Check for an existing message in the rendered template
        self.assertContains(response, "<h1>Payment Canceled</h1>")
        self.assertContains(response, "You have canceled the payment process.")


class PayPalWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("paypal_webhook")
        cls.client = Client()

        # Create a valid Product with UUID
        cls.product = Product.objects.create(
            id=uuid.uuid4(),  # Generate a valid UUID
            product_id="PRD-001",
            name="Recurring Donation",
            price=10.00,
            type="SERVICE",
            category="DONATIONS",
        )

        # Create Plan associated with the Product
        cls.plan = Plan.objects.create(
            id=uuid.uuid4(),  # Generate a valid UUID
            plan_id="P-12345",
            product=cls.product,  # Use the product created above
            name="Monthly Donation",
            amount=10.00,
            interval_unit="MONTH",
            interval_count=1,
            currency="GBP",
        )

        # Create a Donor
        cls.donor = Donor.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )

    def setUp(self):
        """Setup reusable headers and request."""
        self.headers = {"Content-Type": "application/json"}
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    def test_subscription_created_event(self):
        """Test BILLING.SUBSCRIPTION.CREATED event handling."""
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.CREATED",
            "resource": {
                "id": "SUB-001",
                "plan_id": self.plan.plan_id,
                "subscriber": {"email_address": self.donor.email},
            },
        }

        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "subscription_created"})
        self.assertEqual(Subscription.objects.count(), 1)

        # Verify Subscription Details
        subscription = Subscription.objects.first()
        self.assertEqual(subscription.subscription_id, "SUB-001")
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.donor, self.donor)
        self.assertEqual(subscription.status, "ACTIVE")

    def test_subscription_cancelled_event(self):
        """Test BILLING.SUBSCRIPTION.CANCELLED event handling."""
        # Create an active subscription
        subscription = Subscription.objects.create(
            subscription_id="SUB-001",
            plan=self.plan,
            donor=self.donor,
            status="ACTIVE",
        )

        payload = {
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {"id": "SUB-001"},
        }

        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "subscription_cancelled"})

        # Verify Subscription Status
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "CANCELLED")

    def test_subscription_suspended_event(self):
        """Test BILLING.SUBSCRIPTION.SUSPENDED event handling."""
        # Create an active subscription
        subscription = Subscription.objects.create(
            subscription_id="SUB-001",
            plan=self.plan,
            donor=self.donor,
            status="ACTIVE",
        )

        payload = {
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "resource": {"id": "SUB-001"},
        }

        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "subscription_suspended"})

        # Verify Subscription Status
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "SUSPENDED")

    def test_payment_completed_event(self):
        """Test PAYMENT.SALE.COMPLETED event handling."""
        payload = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "billing_agreement_id": "SUB-001",
                "amount": {"total": "10.00", "currency": "GBP"},
            },
        }

        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "payment_completed"})

    def test_unhandled_event_type(self):
        """Test unhandled event type is ignored."""
        payload = {"event_type": "UNKNOWN.EVENT", "resource": {}}

        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "event_ignored"})

    def test_invalid_json_payload(self):
        """Test invalid JSON payload returns 400."""
        response = self.client.post(
            self.url, data="INVALID_JSON", content_type="application/json"
        )

        # Assertions
        self.assertEqual(response.status_code, 400)

    def test_invalid_http_method(self):
        """Test unsupported HTTP method returns 405."""
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 405)


class GetSubscriptionDetailsTests(TestCase):
    @patch("payments.utils.requests.get")
    @patch("payments.views.get_access_token")
    def test_get_subscription_details_success(self, mock_get_access_token, mock_get):
        """
        Test that subscription details are fetched successfully.
        """
        # Mock the access token
        mock_get_access_token.return_value = "mock_access_token"

        # Mock the response for the GET request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "I-SUB12345",
            "status": "ACTIVE",
            "plan_id": "P-12345",
        }
        mock_get.return_value = mock_response

        # Call the function under test
        response = get_subscription_details("I-SUB12345")

        # Assertions
        self.assertEqual(response["id"], "I-SUB12345")
        self.assertEqual(response["status"], "ACTIVE")
        self.assertEqual(response["plan_id"], "P-12345")

        # Verify the mocks were called correctly
        mock_get_access_token.assert_called_once()  # Confirm token was fetched
        mock_get.assert_called_once_with(
            "https://api-m.sandbox.paypal.com/v1/billing/subscriptions/I-SUB12345",
            headers={"Authorization": "Bearer mock_access_token"},
        )

    @patch("payments.views.get_access_token")
    @patch("payments.utils.requests.get")
    def test_get_subscription_details_not_found(self, mock_get, mock_get_access_token):
        """
        Test that 404 Not Found raises an HTTPError.
        """
        # Mock access token retrieval
        mock_get_access_token.return_value = "mock_access_token"

        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error: Not Found for url"
        )
        mock_get.return_value = mock_response

        # Test function
        with self.assertRaises(requests.exceptions.HTTPError):
            get_subscription_details("invalid_id")

        # Verify mocks
        mock_get_access_token.assert_called_once()
        mock_get.assert_called_once()

    @patch("payments.views.get_access_token")
    @patch("payments.utils.requests.get")
    def test_get_subscription_details_network_error(
        self, mock_get, mock_get_access_token
    ):
        """
        Test network error raises RequestException.
        """
        # Mock access token retrieval
        mock_get_access_token.return_value = "mock_access_token"

        # Simulate network error
        mock_get.side_effect = requests.exceptions.RequestException("Network Error")

        # Test function
        with self.assertRaises(requests.exceptions.RequestException):
            get_subscription_details("I-SUB12345")

        # Verify mocks
        mock_get_access_token.assert_called_once()
        mock_get.assert_called_once()


class SubscriptionSuccessViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("subscription_success")
        cls.subscription_id = "I-SUB12345"
        cls.product = Product.objects.create(
            product_id="PRD-12345",
            name="Test Product",
            price=10.00,
            type="SERVICE",
            category="DONATIONS",
        )
        cls.plan = Plan.objects.create(
            plan_id="P-12345",
            product=cls.product,
            name="Test Plan",
            amount=10.00,
            interval_unit="MONTH",
            interval_count=1,
            currency="GBP",
        )

    def setUp(self):
        """Setup logger to suppress logs during tests."""
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    @patch("payments.views.get_subscription_details")
    @patch("payments.views.send_mail")
    def test_subscription_success_creates_subscription_and_sends_email(
        self, mock_send_mail, mock_get_subscription_details
    ):
        """
        Verify that a subscription is created and an email is sent after successful processing.
        """

        mock_get_subscription_details.return_value = {
            "id": self.subscription_id,
            "status": "ACTIVE",
            "plan_id": "P-12345",
            "subscriber": {"email_address": "john.doe@example.com"},
            "start_time": "2023-12-21T10:00:00Z",
            "update_time": "2023-12-21T10:00:00Z",
        }

        response = self.client.get(self.url, {"subscription_id": self.subscription_id})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/subscription_success.html")

        subscription = Subscription.objects.get(subscription_id=self.subscription_id)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, "ACTIVE")
        self.assertEqual(subscription.donor.email, "john.doe@example.com")

        mock_send_mail.assert_called_once_with(
            subject="Thank you for subscribing!",
            message=(
                "Dear Unknown,\n\n"
                'Thank you for joining us and subscribing to the "Test Plan" plan!\n\n'
                "Your subscription details are as follows:\n"
                "- Subscription ID: I-SUB12345\n"
                "- Plan: Test Plan\n"
                "- Amount: £10.00 GBP\n"
                "- Billing Frequency: Every 1 month(s)\n\n"
                "Your support means so much to us and helps us continue making a difference. "
                "If you have any questions or need assistance, feel free to reach out.\n\n"
                "Thank you for being a part of our community!\n\n"
                "Warm regards,\n"
                "The Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["john.doe@example.com"],
        )

    @patch("payments.views.get_subscription_details")
    def test_subscription_success_not_found(self, mock_get_subscription_details):
        """
        Verify behaviour when the subscription is not found.
        """
        mock_get_subscription_details.return_value = None

        response = self.client.get(self.url, {"subscription_id": "INVALID_ID"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/subscription_error.html")
        self.assertContains(response, "Subscription details not found.")

    def test_subscription_success_no_subscription_id(self):
        """
        Verify error when subscription_id is missing.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/subscription_error.html")
        self.assertContains(response, "Missing subscription ID.")


class SubscriptionCancelViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("subscription_cancel")

    def setUp(self):
        """Setup logger to suppress logs during tests."""
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    def test_subscription_cancel_renders_correct_template(self):
        """
        Verify the subscription cancel page uses the correct template.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/subscription_cancel.html")

    def test_subscription_cancel_contains_message(self):
        """
        Verify the cancel page contains an appropriate message.
        """
        response = self.client.get(self.url)
        self.assertContains(response, "You have canceled the subscription process.")


class DonorPageViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="testuser", password="password")
        cls.permission = Permission.objects.get(codename="view_donor")
        cls.user.user_permissions.add(cls.permission)
        cls.donor = Donor.objects.create(
            first_name="John", last_name="Doe", email="john.doe@example.com"
        )
        cls.url = reverse("donor_details", args=[cls.donor.id])

    def setUp(self):
        """Setup logger to suppress logs during tests."""
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """Restore logger settings after each test."""
        self.logger.setLevel(logging.DEBUG)

    def test_donor_page_view(self):
        """Verify the donor page view loads correctly."""
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.url)

        # Check HTTP status code
        self.assertEqual(response.status_code, 200)

        # Check the template used
        self.assertTemplateUsed(response, "payments/donor.html")

        # Verify content is rendered
        self.assertContains(response, "Doe, John")
        self.assertContains(response, "john.doe@example.com")
        self.assertContains(response, "<h3>Donation History</h3>")

        # Verify an empty donation message
        self.assertContains(response, "<em>No donations found for this donor.</em>")

    def test_url_exists_at_correct_location(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_access_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_access_requires_permission(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_donor_details_displayed(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.url)
        self.assertContains(response, "Doe, John")
        self.assertContains(response, "john.doe@example.com")
