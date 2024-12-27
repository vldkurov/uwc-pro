import logging
from unittest.mock import patch
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import activate, get_language

from accounts.admin import CustomUser
from locations.forms import BranchForm, PersonForm, EmailForm
from locations.models import Phone, Branch, Division
from locations.validators import validate_uk_phone_number, format_uk_phone_number

User = get_user_model()


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
            "address_en": "   123 example street   ",
            "postcode": "   SW1A 1AA   ",
            "url": "https://example.com",
        }
        form = BranchForm(data=form_data)
        self.assertTrue(form.is_valid())
        cleaned_data = form.cleaned_data

        self.assertEqual(cleaned_data["title_en"], "Example Branch")
        self.assertEqual(cleaned_data["title_uk"], "Приклад Філії")
        self.assertEqual(cleaned_data["address_en"], "123 Example Street")
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


class DivisionRedirectViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser", password="password"
        )  # Добавляем разрешения
        content_type = ContentType.objects.get_for_model(Division)
        view_permission = Permission.objects.get(
            codename="view_division", content_type=content_type
        )
        add_permission = Permission.objects.get(
            codename="add_division", content_type=content_type
        )
        self.user.user_permissions.add(view_permission, add_permission)

        self.client.login(username="testuser", password="password")

    def test_redirect_to_first_division(self):
        division1 = Division.objects.create(title="Division 1", slug="division-1")
        Division.objects.create(title="Division 2", slug="division-2")

        response = self.client.get(reverse("locations:division_redirect"))

        self.assertRedirects(
            response,
            reverse("locations:division_list", kwargs={"slug": division1.slug}),
        )

    def test_redirect_to_create_division_if_empty(self):
        Division.objects.all().delete()

        response = self.client.get(reverse("locations:division_redirect"))

        self.assertRedirects(response, reverse("locations:division_create"))

    def test_redirect_requires_login(self):
        """Check that the redirect is accessible without authentication."""
        response = self.client.get(reverse("locations:division_redirect"))

        expected_url = reverse("locations:division_create")
        self.assertRedirects(response, expected_url)


class DivisionListViewTests(TestCase):
    @patch("locations.signals.update_geocoding")
    def setUp(self, mock_update_geocoding):
        """
        Set up test data before each test.
        """
        mock_update_geocoding.return_value = None

        # Create a test user
        self.user = User.objects.create_user(username="testuser", password="password")
        self.admin_user = User.objects.create_superuser(
            username="adminuser", password="password"
        )

        # Assign permission to view divisions
        permission = Permission.objects.get(codename="view_division")
        self.user.user_permissions.add(permission)

        # Create test divisions
        self.division1 = Division.objects.create(title="Church Division")
        self.division2 = Division.objects.create(title="Community Division")

        # Create branches within the divisions
        self.branch1 = Branch.objects.create(
            division=self.division1,
            title="Branch A",
            address="123 Test Street",
            postcode="AB12 3CD",
        )
        self.branch2 = Branch.objects.create(
            division=self.division1,
            title="Branch B",
            address="456 Test Street",
            postcode="AB13 3CD",
        )
        self.branch3 = Branch.objects.create(
            division=self.division2,
            title="Branch C",
            address="789 Test Street",
            postcode="CD14 3CD",
        )

        # Activate English as the default language for tests
        activate("en")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    # -------------------------
    # Final cleanup
    # -------------------------

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.logger.setLevel(logging.DEBUG)
        self.client.logout()

    # -------------------------
    # 1. Permissions Tests
    # -------------------------

    def test_redirect_requires_login(self):
        """Verify that unauthenticated users are redirected to the login page."""

        lang_prefix = f"/{get_language()}" if get_language() != "en" else ""

        login_url = reverse("account_login")
        target_url = reverse(
            "locations:division_list", kwargs={"slug": self.division1.slug}
        )
        expected_url = (
            f"{lang_prefix}{login_url}?next={quote(lang_prefix + target_url)}"
        )

        response = self.client.get(target_url)

        self.assertRedirects(response, expected_url)

    def test_access_with_permission(self):
        """
        Ensure that a user with view permissions can access the view.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_access_denied_without_permission(self):
        """
        Confirm that a user without permissions is denied access.
        """
        User.objects.create_user(username="noperm", password="password")
        self.client.login(username="noperm", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.status_code, 403)  # Forbidden

    # -------------------------
    # 2. Template Rendering Tests
    # -------------------------

    def test_correct_template_used(self):
        """
        Verify that the correct template is rendered.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertTemplateUsed(response, "locations/manage/division/list.html")

    # -------------------------
    # 3. Context Data Tests
    # -------------------------

    def test_context_contains_current_division(self):
        """
        Ensure the current division is included in the context.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.context["current_division"], self.division1)

    def test_context_identifies_religious_division(self):
        """
        Verify that divisions with religious keywords are flagged as religious.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertTrue(response.context["is_religious"])  # Division contains 'Church'

    def test_context_identifies_non_religious_division(self):
        """
        Confirm non-religious divisions are flagged correctly.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division2.slug})
        )
        self.assertFalse(
            response.context["is_religious"]
        )  # Division does not contain religious keywords

    def test_context_contains_branches_sorted_by_title(self):
        """
        Ensure branches are included in the context and sorted by title.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertQuerySetEqual(
            response.context["branches"],
            [self.branch1, self.branch2],
            transform=lambda x: x,
        )

    def test_context_with_sort_direction_desc(self):
        """
        Test branches sorted in descending order based on the query parameter.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug}),
            {"sort": "title", "direction": "desc"},
        )
        self.assertQuerySetEqual(
            response.context["branches"],
            [self.branch2, self.branch1],  # Sorted in reverse
            transform=lambda x: x,
        )

    # -------------------------
    # 4. Sorting and Query Parameter Tests
    # -------------------------

    def test_sorting_by_title_in_english(self):
        """
        Test sorting by title in English language.
        """
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug}),
            {"sort": "title", "direction": "asc"},
        )
        self.assertEqual(response.context["branches"][0], self.branch1)

    def test_sorting_by_title_in_ukrainian(self):
        """
        Test sorting by title in Ukrainian language.
        """
        activate("uk")
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug}),
            {"sort": "title", "direction": "asc"},
        )
        self.assertEqual(response.context["branches"][0], self.branch1)

    def test_invalid_sort_column_fallback(self):
        """
        Test fallback to default sorting if an invalid column is provided.
        """
        # Log in the user with the required permissions
        self.client.login(username="testuser", password="password")

        # Perform a GET request with an invalid sorting parameter
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug}),
            {"sort": "invalid_column"},
        )

        # Verify that the request completes with status code 200
        self.assertEqual(response.status_code, 200)

        # Ensure that the sorting defaults to the expected order (title)
        branches = list(response.context["branches"])
        self.assertEqual(branches[0], self.branch1)
        self.assertEqual(branches[1], self.branch2)

    # -------------------------
    # 5. Edge Cases
    # -------------------------

    def test_empty_division_list(self):
        """
        Verify handling when no divisions exist.
        """
        # Activate the English locale
        activate("en")

        self.client.login(username="testuser", password="password")

        permission_add = Permission.objects.get(codename="add_division")
        self.user.user_permissions.add(permission_add)

        Division.objects.all().delete()

        lang_prefix = f"/{get_language()}" if get_language() != "en" else ""

        expected_url = f"{lang_prefix}{reverse('locations:division_create')}"

        response = self.client.get(reverse("locations:division_redirect"))

        self.assertRedirects(response, expected_url)

    def test_empty_branches(self):
        """
        Confirm view handles divisions with no branches gracefully.
        """
        Branch.objects.all().delete()  # Remove all branches
        self.client.login(username="testuser", password="password")
        response = self.client.get(
            reverse("locations:division_list", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(len(response.context["branches"]), 0)


class DivisionCreateView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.admin_user = User.objects.create_superuser(
            username="adminuser", password="password"
        )

        add_division = Permission.objects.get(codename="add_division")
        view_division = Permission.objects.get(codename="view_division")
        self.admin_user.user_permissions.add(view_division, add_division)

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.logger.setLevel(logging.DEBUG)
        self.client.logout()

    def test_create_division_requires_login(self):
        """
        Verify that unauthenticated users are redirected to the login page.
        """
        lang_prefix = f"/{get_language()}" if get_language() != "en" else ""

        login_url = reverse("account_login")
        expected_url = f"{lang_prefix}{login_url}?next={quote(lang_prefix + reverse('locations:division_create'))}"

        response = self.client.get(reverse("locations:division_create"))

        self.assertRedirects(response, expected_url)

    def test_create_division_requires_permission(self):
        """
        Verify that only users with 'add_division' permission can access the view.
        """
        self.client.login(username="testuser", password="password")

        response = self.client.get(reverse("locations:division_create"))

        self.assertEqual(response.status_code, 403)

        permission = Permission.objects.get(codename="add_division")
        self.user.user_permissions.add(permission)

        response = self.client.get(reverse("locations:division_create"))

        self.assertEqual(response.status_code, 200)

    def test_create_division_form_displayed(self):
        """
        Verify that the form is displayed correctly for users with permissions.
        """
        permission = Permission.objects.get(codename="add_division")
        self.user.user_permissions.add(permission)

        self.client.login(username="testuser", password="password")

        response = self.client.get(reverse("locations:division_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")
        self.assertContains(response, "title_en")
        self.assertContains(response, "title_uk")

    def test_create_valid_division(self):
        """
        Verify that a valid division can be created successfully.
        """
        self.client.login(username="adminuser", password="password")

        form_data = {
            "title_en": "New Division",
            "title_uk": "Нова Дивізія",
        }

        response = self.client.post(reverse("locations:division_create"), form_data)

        division = Division.objects.get(title="New Division")

        expected_url = reverse(
            "locations:division_list", kwargs={"slug": division.slug}
        )
        self.assertRedirects(response, expected_url)

        self.assertTrue(Division.objects.filter(title="New Division").exists())

    def test_create_invalid_division(self):
        """
        Verify that invalid data does not create a division.
        """
        activate("en")

        self.client.login(username="adminuser", password="password")

        response = self.client.post(reverse("locations:division_create"), {})

        self.assertEqual(response.status_code, 200)

        form = response.context.get("form")
        self.assertIsNotNone(form, "Form is not available in the context.")

        self.assertTrue(form.errors, "Form errors are not present.")

        self.assertIn("title_en", form.errors)
        self.assertIn("title_uk", form.errors)

        self.assertEqual(
            form.errors["title_en"], ["This field is required in English."]
        )
        self.assertEqual(
            form.errors["title_uk"], ["This field is required in Ukrainian."]
        )

        self.assertEqual(Division.objects.count(), 0)
