from django.core.exceptions import ValidationError
from django.test import TestCase

from locations.forms import BranchForm, PersonForm, EmailForm
from locations.models import Phone, Branch, Division
from locations.validators import validate_uk_phone_number, format_uk_phone_number


class PostcodeValidationTest(TestCase):
    def test_valid_postcode(self):
        form = BranchForm(data={"postcode": "sw1a1aa"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["postcode"], "SW1A 1AA")

    def test_invalid_postcode(self):
        form = BranchForm(data={"postcode": "invalid"})
        self.assertFalse(form.is_valid())
        self.assertIn("Please enter a valid UK postcode.", form.errors["postcode"])

    def test_formatting_postcode(self):
        form = BranchForm(data={"postcode": "ec1a1bb"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["postcode"], "EC1A 1BB")


class BranchFormTests(TestCase):
    def test_branch_form_sanitization(self):
        form_data = {
            "title_en": "   example branch   ",
            "title_uk": "   приклад філії   ",
            "address": "   123 example street   ",
            "postcode": "   SW1A 1AA   ",
            "url": "https://example.com",
        }
        form = BranchForm(data=form_data)
        self.assertTrue(form.is_valid())
        cleaned_data = form.cleaned_data

        self.assertEqual(cleaned_data["title_en"], "Example Branch")
        self.assertEqual(cleaned_data["title_uk"], "Приклад Філії")
        self.assertEqual(cleaned_data["address"], "123 Example Street")
        self.assertEqual(cleaned_data["postcode"], "SW1A 1AA")


class PersonFormTests(TestCase):
    def test_person_form_sanitization(self):
        form_data = {
            "first_name_en": "   john   ",
            "last_name_en": "   doe   ",
            "first_name_uk": "   іван   ",
            "last_name_uk": "   петренко   ",
        }
        form = PersonForm(data=form_data)
        self.assertTrue(form.is_valid())
        cleaned_data = form.cleaned_data

        self.assertEqual(cleaned_data["first_name_en"], "John")
        self.assertEqual(cleaned_data["last_name_en"], "Doe")
        self.assertEqual(cleaned_data["first_name_uk"], "Іван")
        self.assertEqual(cleaned_data["last_name_uk"], "Петренко")


class UKPhoneNumberTests(TestCase):
    def test_valid_uk_phone_numbers(self):
        valid_numbers = [
            "+44 20 7946 0958",
            "020 7946 0958",
            "+44 7911 123456",
            "07911 123456",
        ]
        for number in valid_numbers:
            formatted = format_uk_phone_number(number)
            validate_uk_phone_number(formatted)
            self.assertTrue(formatted.startswith("+44"))

    def test_invalid_phone_numbers(self):
        invalid_numbers = [
            "123456",
            "00 123 456 789",
            "+44 123 456",
        ]
        for number in invalid_numbers:
            with self.assertRaises(ValidationError):
                validate_uk_phone_number(number)

    def test_model_sanitization(self):
        division = Division.objects.create(title="Test Division", slug="test-division")

        branch = Branch.objects.create(
            title="Test Branch",
            slug="test-branch",
            address="123 Test Street",
            postcode="AB12 3CD",
            division=division,
        )

        phone = Phone(number="07911123456", branch=branch)
        phone.save()

        self.assertEqual(phone.number, "+44 7911 123456")


class EmailFormTests(TestCase):
    def test_email_sanitization(self):
        form_data = {"email": "   Test@Example.COM  "}
        form = EmailForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["email"], "test@example.com")

    def test_invalid_email(self):
        form_data = {"email": "invalid-email"}
        form = EmailForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
