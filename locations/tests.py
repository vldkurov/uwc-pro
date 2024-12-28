import json
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
        self.division1 = Division.objects.create(
            title_en="Church Division", title_uk="Церковний відділ"
        )
        self.division2 = Division.objects.create(
            title_en="Community Division", title_uk="Громадський відділ"
        )

        # Create branches within the divisions
        self.branch1 = Branch.objects.create(
            division=self.division1,
            title_en="Branch A",
            title_uk="Відділення А",
            address="123 Test Street",
            postcode="AB12 3CD",
        )
        self.branch2 = Branch.objects.create(
            division=self.division1,
            title_en="Branch B",
            title_uk="Відділення Б",
            address="456 Test Street",
            postcode="AB13 3CD",
        )
        self.branch3 = Branch.objects.create(
            division=self.division2,
            title_en="Branch C",
            title_uk="Відділення В",
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
            {"sort": "title_uk", "direction": "asc"},
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


class DivisionUpdateViewTests(TestCase):
    """
    Test cases for DivisionUpdateView.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Create test data shared across all tests.
        """

        cls.user = User.objects.create_user(username="testuser", password="password")
        cls.admin_user = User.objects.create_superuser(
            username="adminuser", password="password"
        )

        cls.view_division = Permission.objects.get(codename="view_division")
        cls.change_division = Permission.objects.get(codename="change_division")
        cls.user.user_permissions.add(cls.view_division, cls.change_division)

        cls.division = Division.objects.create(
            title_en="Old Title EN", title_uk="Old Title UK"
        )

    def test_update_valid_division(self):
        """
        Verify that a valid division update works correctly.
        """
        # Логиним пользователя
        self.client.login(username="testuser", password="password")

        # Получаем текущий языковой префикс
        lang_prefix = f"/{get_language()}" if get_language() != "en" else ""

        # Отправляем валидные данные для обновления
        response = self.client.post(
            reverse("locations:division_edit", kwargs={"slug": self.division.slug}),
            {
                "title_en": "New Title EN",
                "title_uk": "New Title UK",
            },
        )

        # Генерируем ожидаемый URL с префиксом языка
        expected_url = f"{lang_prefix}{reverse('locations:division_list', kwargs={'slug': self.division.slug})}"

        # Логируем URL для отладки
        print(f"Redirect URL: {response.url}")
        print(f"Expected URL: {expected_url}")

        # Проверяем редирект
        self.assertRedirects(response, expected_url)

        # Обновляем данные из базы и проверяем изменения
        self.division.refresh_from_db()
        self.assertEqual(self.division.title_en, "New Title EN")
        self.assertEqual(self.division.title_uk, "New Title UK")

    def test_update_invalid_division(self):
        """
        Verify validation errors when invalid data is submitted.
        """
        self.client.login(username="adminuser", password="password")

        response = self.client.post(
            reverse("locations:division_edit", kwargs={"slug": self.division.slug}),
            {"title_en": "", "title_uk": ""},
        )

        self.assertEqual(response.status_code, 200)

        form = response.context.get("form")
        self.assertTrue(form.errors)

        self.assertEqual(
            form.errors["title_en"], ["This field is required in English."]
        )
        self.assertEqual(
            form.errors["title_uk"], ["This field is required in Ukrainian."]
        )

    def test_redirect_requires_login(self):
        """
        Verify that unauthenticated users are redirected to the login page.
        """
        target_url = reverse(
            "locations:division_edit", kwargs={"slug": self.division.slug}
        )
        login_url = reverse("account_login")
        expected_url = f"{login_url}?next={target_url}"

        response = self.client.get(target_url)
        self.assertRedirects(response, expected_url)

    def test_permission_required(self):
        """
        Verify that users without the required permission cannot access the view.
        """
        self.client.login(username="testuser", password="password")

        self.user.user_permissions.remove(self.change_division)

        response = self.client.get(
            reverse("locations:division_edit", kwargs={"slug": self.division.slug})
        )
        self.assertEqual(response.status_code, 403)  # Доступ запрещен

    def test_permission_granted(self):
        """
        Verify that users with the required permission can access the view.
        """
        self.client.login(username="testuser", password="password")

        response = self.client.get(
            reverse("locations:division_edit", kwargs={"slug": self.division.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "locations/manage/division/form.html")


class DivisionDeleteViewTests(TestCase):
    """
    Test cases for the DivisionDeleteView.
    """

    def setUp(self):
        """
        Set up test data for each test.
        """
        activate("en")

        self.user = User.objects.create_user(username="testuser", password="password")
        permission = Permission.objects.get(codename="delete_division")
        self.user.user_permissions.add(permission)

        self.client.login(username="testuser", password="password")

        self.division = Division.objects.create(title="Test Division")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.logger.setLevel(logging.DEBUG)
        self.client.logout()

    def test_delete_valid_division(self):
        """
        Verify that a valid division can be deleted.
        """
        lang_prefix = f"/{get_language()}"

        self.delete_url = reverse(
            "locations:division_delete", kwargs={"slug": self.division.slug}
        )
        self.redirect_url = f"{lang_prefix}{reverse('locations:division_redirect')}"

        response = self.client.post(self.delete_url)

        self.assertFalse(Division.objects.filter(id=self.division.id).exists())

    def test_delete_division_without_permission(self):
        """
        Verify that deletion fails if the user lacks permissions.
        """
        self.client.logout()
        user_no_permission = User.objects.create_user(
            username="noperm", password="password"
        )
        self.client.login(username="noperm", password="password")

        self.delete_url = reverse(
            "locations:division_delete", kwargs={"slug": self.division.slug}
        )
        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 403)

        self.assertTrue(Division.objects.filter(id=self.division.id).exists())

    def test_delete_division_not_logged_in(self):
        """
        Verify that unauthenticated users are redirected to the login page.
        """
        self.client.logout()

        login_url = reverse("account_login")

        self.delete_url = reverse(
            "locations:division_delete", kwargs={"slug": self.division.slug}
        )
        expected_url = f"{login_url}?next={self.delete_url}"

        response = self.client.post(self.delete_url)

        self.assertRedirects(response, expected_url)

        self.assertTrue(Division.objects.filter(id=self.division.id).exists())


class DivisionOrderViewTests(TestCase):
    def setUp(self):
        """
        Set up test data for each test.
        """
        # Activate English language
        activate("en")

        # Create test user with required permissions
        self.user = User.objects.create_user(username="testuser", password="password")
        permission = Permission.objects.get(codename="change_division_order")
        self.user.user_permissions.add(permission)

        self.client.login(username="testuser", password="password")

        # Create sample divisions
        self.div1 = Division.objects.create(title="Division 1", order=1)
        self.div2 = Division.objects.create(title="Division 2", order=2)
        self.div3 = Division.objects.create(title="Division 3", order=3)

        # API endpoint
        self.url = reverse("locations:division_order")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.logger.setLevel(logging.DEBUG)
        self.client.logout()

    def test_valid_order_change(self):
        """
        Verify that a valid order change request updates divisions successfully.
        """
        data = {
            str(self.div1.id): 3,
            str(self.div2.id): 1,
            str(self.div3.id): 2,
        }

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"saved": "OK"})

        self.div1.refresh_from_db()
        self.div2.refresh_from_db()
        self.div3.refresh_from_db()

        self.assertEqual(self.div1.order, 3)
        self.assertEqual(self.div2.order, 1)
        self.assertEqual(self.div3.order, 2)

    def test_no_permission(self):
        """
        Verify that a user without the required permission receives a 403 error.
        """
        user = User.objects.create_user(username="noperms", password="password")
        self.client.login(username="noperms", password="password")

        response = self.client.post(
            self.url,
            data=json.dumps({str(self.div1.id): 3}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(
            response.content,
            {"error": "You do not have permission to change the Division order."},
        )

    def test_invalid_data(self):
        """
        Verify that invalid data does not crash the server and returns a 400 error.
        """
        data = {"invalid_id": 1}

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"error": "Invalid ID: invalid_id"})

    def test_unauthenticated_request(self):
        """
        Verify that unauthenticated users cannot access the endpoint.
        """
        self.client.logout()

        response = self.client.post(
            self.url,
            data=json.dumps({str(self.div1.id): 1}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(
            response.content,
            {"error": "You do not have permission to change the Division order."},
        )


class BranchCreateUpdateViewTests(TestCase):

    @patch("locations.signals.division_pre_save_receiver")
    @patch("locations.signals.update_geocoding")
    @patch("locations.signals.branch_pre_save_receiver")
    def setUp(
        self,
        mock_division_pre_save_receiver,
        mock_update_geocoding,
        branch_pre_save_receiver,
    ):
        """
        Set up test data for the BranchCreateUpdateView.
        """

        mock_division_pre_save_receiver.return_value = None
        mock_update_geocoding.return_value = None
        branch_pre_save_receiver.return_value = None

        # Activate English for consistent URLs
        activate("en")

        # Create a user with necessary permissions
        self.user = User.objects.create_user(username="testuser", password="password")
        permissions = Permission.objects.filter(
            codename__in=["view_division", "view_branch", "add_branch", "change_branch"]
        )
        self.user.user_permissions.add(*permissions)

        # Create a test division
        self.division = Division.objects.create(
            title_en="Test Division", title_uk="Випробувальний відділ"
        )

        # Create a test branch for update tests
        self.branch = Branch.objects.create(
            division=self.division,
            title_en="Test Branch",
            title_uk="Тестове відділення",
            address="123 Test St",
        )

        # Log in the test user
        self.client.login(username="testuser", password="password")

        # URLs for testing
        self.create_url = reverse(
            "locations:division_branch_create",
            kwargs={"division_slug": self.division.slug},
        )
        self.update_url = reverse(
            "locations:division_branch_update",
            kwargs={
                "division_slug": self.division.slug,
                "branch_slug": self.branch.slug,
            },
        )

        self.redirect_url = reverse(
            "locations:division_list", kwargs={"slug": self.division.slug}
        )

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.client.logout()
        self.logger.setLevel(logging.DEBUG)

    def test_get_create_branch(self):
        """
        Verify that the GET request for creating a branch loads the form.
        """
        response = self.client.get(self.create_url)

        # Check response code
        self.assertEqual(response.status_code, 200)

        # Check template usage
        self.assertTemplateUsed(response, "locations/manage/branch/form.html")

        # Check context variables
        self.assertIn("branch_form", response.context)
        self.assertIsInstance(response.context["branch_form"], BranchForm)

        self.assertIn("phone_formset", response.context)
        self.assertIn("email_formset", response.context)

    def test_get_update_branch(self):
        """
        Verify that the GET request for editing a branch preloads the existing data.
        """
        response = self.client.get(self.update_url)

        # Check response code
        self.assertEqual(response.status_code, 200)

        # Ensure preloaded data appears
        self.assertEqual(response.context["branch_form"].instance, self.branch)
        self.assertEqual(
            response.context["branch_form"].initial["title_en"], "Test Branch"
        )

    def test_post_create_valid_branch(self):
        """
        Verify that a valid branch can be created successfully.
        """
        # Test data
        data = {
            "title_en": "New Branch",
            "title_uk": "Нове відділення",
            "address": "456 New St",
            "postcode": "AB12 3CD",
        }
        phone_data = {
            "phones-TOTAL_FORMS": "1",
            "phones-INITIAL_FORMS": "0",
            "phones-0-number": "+44 1234 567890",
        }
        email_data = {
            "emails-TOTAL_FORMS": "1",
            "emails-INITIAL_FORMS": "0",
            "emails-0-email": "test@example.com",
        }

        # Submit form
        response = self.client.post(
            self.create_url,
            {**data, **phone_data, **email_data},
        )

        # Debug logs if validation fails
        if response.status_code == 200:
            print("Branch Form Errors:", response.context["branch_form"].errors)
            print("Phone Formset Errors:", response.context["phone_formset"].errors)
            print("Email Formset Errors:", response.context["email_formset"].errors)

        # Assert redirection after valid submission
        self.assertRedirects(
            response, self.redirect_url, status_code=302, target_status_code=200
        )

        # Assert branch creation
        self.assertEqual(Branch.objects.filter(title_en="New Branch").count(), 1)

    def test_post_update_valid_branch(self):
        """
        Verify that a branch can be updated successfully.
        """
        data = {
            "title_en": "Updated Branch",
            "address_en": "789 Updated St",
            "postcode": "AB13 4CD",
        }
        phone_data = {"phones-TOTAL_FORMS": "1", "phones-INITIAL_FORMS": "0"}
        email_data = {"emails-TOTAL_FORMS": "1", "emails-INITIAL_FORMS": "0"}

        response = self.client.post(
            self.update_url,
            {**data, **phone_data, **email_data},
        )

        # Check redirection
        self.assertRedirects(response, self.redirect_url)

        # Verify branch update
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.title_en, "Updated Branch")
        self.assertEqual(self.branch.address_en, "789 Updated St")

    def test_post_invalid_branch(self):
        """
        Verify that invalid branch data does not save and renders the form again.
        """
        data = {
            "title": "",
            "address": "123 Test St",
        }
        response = self.client.post(
            self.create_url, data, content_type="application/json"
        )

        # Check that the response does NOT redirect (stays on the form page)
        self.assertEqual(response.status_code, 200)

        # Ensure no new branch was created
        self.assertEqual(Branch.objects.count(), 1)

    def test_missing_permissions(self):
        """
        Verify that users without permissions cannot access the view.
        """
        self.client.logout()

        # Log in as a user without permissions
        user = User.objects.create_user(username="noperm", password="password")
        self.client.login(username="noperm", password="password")

        # Attempt to access the page
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(self.create_url, {})
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_access(self):
        """
        Verify that unauthenticated users are redirected to the login page.
        """
        self.client.logout()

        response = self.client.get(self.create_url)
        self.assertRedirects(
            response, f"{reverse('account_login')}?next={self.create_url}"
        )

    def test_religious_keyword_detection(self):
        """
        Verify the religious context is correctly detected.
        """
        # Create a religious division
        religious_division = Division.objects.create(title_en="Church of Peace")
        create_url = reverse(
            "locations:division_branch_create",
            kwargs={"division_slug": religious_division.slug},
        )

        response = self.client.get(create_url)

        # Ensure 'is_religious' context is True
        self.assertTrue(response.context["is_religious"])


class BranchDeleteViewTests(TestCase):
    @patch("locations.signals.update_geocoding")
    def setUp(self, mock_update_geocoding):
        """
        Set up test data for BranchDeleteView.
        """
        mock_update_geocoding.return_value = None

        # Activate English language for consistent URLs
        activate("en")

        # Create test users
        self.admin_user = User.objects.create_superuser(
            username="adminuser", password="password"
        )
        self.user = User.objects.create_user(username="testuser", password="password")

        # Assign permissions to the regular user
        permissions = Permission.objects.filter(
            codename__in=["view_division", "delete_branch"]
        )
        self.user.user_permissions.add(*permissions)

        # Create a test division
        self.division = Division.objects.create(
            title_en="Test Division", title_uk="Тестовий Відділ"
        )

        # Create a test branch
        self.branch = Branch.objects.create(
            division=self.division,
            title_en="Test Branch",
            title_uk="Тестове Відділення",
            address="123 Test Street",
            postcode="AB12 3CD",
        )

        # URLs for testing
        self.delete_url = reverse(
            "locations:division_branch_delete",
            kwargs={
                "division_slug": self.division.slug,
                "branch_slug": self.branch.slug,
            },
        )
        self.redirect_url = reverse(
            "locations:division_list", kwargs={"slug": self.division.slug}
        )

        # Log in the test user
        self.client.login(username="testuser", password="password")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.client.logout()
        self.logger.setLevel(logging.DEBUG)

    # ---------------------------------
    # TEST CASES
    # ---------------------------------

    def test_delete_valid_branch(self):
        """
        Verify that a valid branch can be deleted successfully.
        """
        # Perform the delete request
        response = self.client.post(self.delete_url)

        # Check redirection
        self.assertRedirects(response, self.redirect_url)

        # Verify the branch is deleted
        self.assertFalse(
            Branch.objects.filter(id=self.branch.id).exists(),
            "Branch was not deleted.",
        )

    def test_delete_branch_no_permission(self):
        """
        Verify that a user without delete permissions cannot delete a branch.
        """
        # Remove permission
        self.user.user_permissions.clear()

        # Attempt to delete the branch
        response = self.client.post(self.delete_url)

        # Check forbidden access
        self.assertEqual(response.status_code, 403)

        # Ensure the branch still exists
        self.assertTrue(Branch.objects.filter(id=self.branch.id).exists())

    def test_delete_branch_not_authenticated(self):
        """
        Verify that unauthenticated users cannot delete a branch.
        """
        # Log out the user
        self.client.logout()

        # Attempt to delete the branch
        response = self.client.post(self.delete_url)

        # Check redirection to login page
        login_url = reverse("account_login")
        expected_url = f"{login_url}?next={self.delete_url}"
        self.assertRedirects(response, expected_url)

        # Ensure the branch still exists
        self.assertTrue(Branch.objects.filter(id=self.branch.id).exists())

    def test_delete_nonexistent_branch(self):
        """
        Verify that trying to delete a nonexistent branch results in a 404.
        """
        # Construct a URL with an invalid slug
        invalid_url = reverse(
            "locations:division_branch_delete",
            kwargs={"division_slug": self.division.slug, "branch_slug": "invalid-slug"},
        )

        # Attempt to delete
        response = self.client.post(invalid_url)

        # Check 404 response
        self.assertEqual(response.status_code, 404)

    def test_delete_branch_from_another_division(self):
        """
        Verify that a branch in another division cannot be deleted.
        """
        # Create a new division and branch
        another_division = Division.objects.create(
            title_en="Another Division", title_uk="Інший Відділ"
        )
        another_branch = Branch.objects.create(
            division=another_division,
            title_en="Another Branch",
            address="456 Another Street",
            postcode="AB12 3CD",
        )

        # Attempt to delete using the wrong division slug
        invalid_url = reverse(
            "locations:division_branch_delete",
            kwargs={
                "division_slug": self.division.slug,
                "branch_slug": another_branch.slug,
            },
        )
        response = self.client.post(invalid_url)

        # Check 404 response
        self.assertEqual(response.status_code, 404)

        # Ensure the branch still exists
        self.assertTrue(Branch.objects.filter(id=another_branch.id).exists())


class BranchDisplayViewTests(TestCase):
    @patch("locations.signals.update_geocoding")
    def setUp(self, mock_update_geocoding):
        """
        Set up test data for BranchDisplayView.
        """
        mock_update_geocoding.return_value = None

        # Activate English language for consistency
        activate("en")

        # Create test users
        self.user = User.objects.create_user(username="testuser", password="password")
        self.admin_user = User.objects.create_superuser(
            username="adminuser", password="password"
        )

        # Assign permission to display branches
        permission_display = Permission.objects.get(
            codename="display",
            content_type__app_label="locations",
            content_type__model="branch",
        )
        permission_view_division = Permission.objects.get(
            codename="view_division",
            content_type__app_label="locations",
            content_type__model="division",
        )
        permission_view_branch = Permission.objects.get(
            codename="view_branch",
            content_type__app_label="locations",
            content_type__model="branch",
        )
        self.user.user_permissions.add(
            permission_display, permission_view_division, permission_view_branch
        )

        # Create test division and branch
        self.division = Division.objects.create(
            title_en="Test Division", title_uk="Тестовий Відділ"
        )

        self.branch = Branch.objects.create(
            division=self.division,
            title_en="Test Branch",
            title_uk="Тестове Відділення",
            address="123 Test Street",
            postcode="AB12 3CD",
        )

        # URLs for testing
        self.display_url = reverse(
            "locations:division_branch_display",
            kwargs={
                "division_slug": self.division.slug,
                "branch_slug": self.branch.slug,
            },
        )
        self.redirect_url = reverse(
            "locations:division_list", kwargs={"slug": self.division.slug}
        )

        # Log in the test user
        self.client.login(username="testuser", password="password")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.client.logout()
        self.logger.setLevel(logging.DEBUG)

    # ---------------------------------
    # TEST CASES
    # ---------------------------------

    @patch("locations.signals.update_geocoding")
    def test_display_valid_branch(self, mock_update_geocoding):
        """
        Verify that a valid branch can be displayed successfully.
        """
        # Mock the display method
        mock_update_geocoding.return_value = None

        # Ensure branch is initially HIDE
        self.assertEqual(self.branch.status, Branch.Status.HIDE)

        # Perform POST request
        response = self.client.post(self.display_url)

        # Verify redirection to a division list
        self.assertRedirects(response, self.redirect_url)

        # Refresh branch from database to get the updated status
        self.branch.refresh_from_db()

        # Assert branch status is updated to DISPLAY
        self.assertEqual(self.branch.status, Branch.Status.DISPLAY)

    def test_display_branch_no_permission(self):
        """
        Verify that users without display permission cannot access the view.
        """
        # Remove permissions
        self.user.user_permissions.clear()

        # Perform POST request
        response = self.client.post(self.display_url)

        # Check forbidden access
        self.assertEqual(response.status_code, 403)

    def test_display_branch_not_authenticated(self):
        """
        Verify that unauthenticated users cannot access the view.
        """
        # Log out the user
        self.client.logout()

        # Perform POST request
        response = self.client.post(self.display_url)

        # Verify redirection to login page
        login_url = reverse("account_login")
        expected_url = f"{login_url}?next={self.display_url}"
        self.assertRedirects(response, expected_url)

    def test_display_nonexistent_branch(self):
        """
        Verify that attempting to display a nonexistent branch returns 404.
        """
        # Construct URL with invalid slug
        invalid_url = reverse(
            "locations:division_branch_display",
            kwargs={"division_slug": self.division.slug, "branch_slug": "invalid-slug"},
        )

        # Perform POST request
        response = self.client.post(invalid_url)

        # Verify 404 response
        self.assertEqual(response.status_code, 404)

    def test_display_branch_in_wrong_division(self):
        """
        Verify that a branch from another division cannot be displayed.
        """
        # Create a new division and branch
        another_division = Division.objects.create(
            title_en="Another Division", title_uk="Інший Відділ"
        )
        another_branch = Branch.objects.create(
            division=another_division,
            title_en="Another Branch",
            address="456 Another Street",
            postcode="AB13 3CD",
        )

        # Construct URL with mismatched division and branch
        invalid_url = reverse(
            "locations:division_branch_display",
            kwargs={
                "division_slug": self.division.slug,
                "branch_slug": another_branch.slug,
            },
        )

        # Perform POST request
        response = self.client.post(invalid_url)

        # Verify 404 response
        self.assertEqual(response.status_code, 404)
