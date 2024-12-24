import json
import logging
import os
import uuid
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse, resolve
from django.utils.translation import activate
from django.apps import apps

from accounts.models import CustomUser
from locations.models import Division, Branch, Person
from payments.models import Donor, Donation
from .forms import PageForm
from .models import Page, Section, Content, Text, File, Image as ImageModel, Video, URL
from .views import (
    DashboardView,
    ManagePageListView,
    PageUpdateView,
    PageCreateView,
    PageDeleteView,
    ContentCreateUpdateView,
)


class DashboardTests(TestCase):
    def setUp(self):
        url = reverse("dashboard")
        self.response = self.client.get(url)

    def test_url_exists_at_desired_location(self):
        self.assertEqual(self.response.status_code, 200)

    def test_homepage_template(self):
        self.assertTemplateUsed(self.response, "hub/dashboard.html")

    def test_homepage_contains_correct_html(self):
        self.assertContains(self.response, "UWC Dashboard")

    def test_homepage_does_not_contain_incorrect_html(self):
        self.assertNotContains(self.response, "Hi there! I should not be on the page.")

    def test_homepage_url_resolves_homepageview(self):
        view = resolve("/en/dashboard/")
        self.assertEqual(view.func.__name__, DashboardView.as_view().__name__)


class ManagePageListViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="password",
            role=CustomUser.Role.ADMIN,
        )
        self.user.user_permissions.add(Permission.objects.get(codename="view_page"))
        self.client.login(username="testuser", password="password")
        self.page1 = Page.objects.create(
            title="Page 1", slug="page-1", modified_by=self.user
        )
        self.page2 = Page.objects.create(
            title="Page 2", slug="page-2", modified_by=self.user
        )
        self.url = reverse("manage_page_list")
        self.response = self.client.get(self.url)
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_permission_required(self):
        get_user_model().objects.create_user(
            username="vieweruser",
            password="password",
            role=CustomUser.Role.VIEWER,
        )
        self.client.login(username="vieweruser", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_view_with_permission(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/page/list.html")

    def test_context_data(self):
        self.assertIn("page_list", self.response.context)
        page_list = self.response.context["page_list"]
        self.assertEqual(len(page_list), 2)
        self.assertIn(self.page1, page_list)
        self.assertIn(self.page2, page_list)

    def test_redirect_field(self):
        self.client.logout()
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_page_list_ordering(self):
        page_list = self.response.context["page_list"]
        self.assertEqual(list(page_list), [self.page1, self.page2])

    def test_status_code_and_template_used(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, "hub/manage/page/list.html")

    def test_page_list_url_resolves_managepagelistview_en(self):
        view = resolve("/en/list/")
        self.assertEqual(view.func.__name__, ManagePageListView.as_view().__name__)


class PageCreateViewTest(TestCase):
    def setUp(self):
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_add = Permission.objects.get(codename="add_page")
        permission_view = Permission.objects.get(codename="view_page")
        self.user_with_permission.user_permissions.add(permission_add, permission_view)
        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )
        self.url = reverse("page_create")
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_user_can_create_page(self):
        self.client.login(username="user_with_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_user_cannot_create_page(self):
        self.client.login(username="user_without_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_create_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_view_with_permission(self):
        self.client.login(username="user_with_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/page/form.html")

    def test_valid_form_submission(self):
        self.client.login(username="user_with_permission", password="password")
        data = {
            "title_en": "New Page (EN)",
            "title_uk": "Нова Сторінка (UA)",
        }
        response = self.client.post(self.url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Page.objects.filter(title_en="New Page (EN)").exists())

    def test_invalid_form_submission(self):
        self.client.login(username="user_with_permission", password="password")
        data = {
            "title_en": "",
            "title_uk": "",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        self.assertTrue(form.errors)

        self.assertIn("__all__", form.errors)
        self.assertEqual(form.errors["__all__"], ["Title must be provided."])
        self.assertIn("title_en", form.errors)
        self.assertEqual(form.errors["title_en"], ["This field is required."])
        self.assertIn("title_uk", form.errors)
        self.assertEqual(form.errors["title_uk"], ["This field is required."])

    def test_context_data(self):
        self.client.login(username="user_with_permission", password="password")
        response = self.client.get(self.url)
        self.assertIn("form", response.context)
        self.assertIsInstance(response.context["form"], PageForm)

    def test_redirect_after_successful_creation(self):
        self.client.login(username="user_with_permission", password="password")
        data = {
            "title_en": "Redirect Page (EN)",
            "title_uk": "Сторінка для редиректу (UA)",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("manage_page_list"))

    def test_slug_generation(self):
        self.client.login(username="user_with_permission", password="password")
        data = {
            "title_en": "Page Slug Test (EN)",
            "title_uk": "Тест слугу сторінки (UA)",
        }
        self.client.post(self.url, data)
        page = Page.objects.get(title_en="Page Slug Test (EN)")
        self.assertEqual(page.slug, "page-slug-test-en")

    def test_access_for_different_roles(self):
        roles = ["OWR", "ADM", "EDT", "VWR"]
        for role in roles:
            user = get_user_model().objects.create_user(
                username=f"user_{role}",
                password="password",
                role=role,
            )
            if role in ["OWR"]:
                user.user_permissions.add(Permission.objects.get(codename="add_page"))
            self.client.login(username=f"user_{role}", password="password")
            response = self.client.get(self.url)
            if role in ["OWR"]:
                self.assertEqual(response.status_code, 200)
            else:
                self.assertEqual(response.status_code, 403)

    def test_url_resolves_to_view(self):
        view = resolve("/en/dashboard/hub/create/")
        self.assertEqual(view.func.__name__, PageCreateView.as_view().__name__)


class PageUpdateViewTest(TestCase):
    def setUp(self):
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_change = Permission.objects.get(codename="change_page")
        permission_view = Permission.objects.get(codename="view_page")
        self.user_with_permission.user_permissions.add(
            permission_change, permission_view
        )
        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )
        self.page = Page.objects.create(
            title="Test Page",
            slug="test-page",
            modified_by=self.user_with_permission,
        )
        self.url = reverse("page_edit", kwargs={"slug": self.page.slug})
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def login_user_with_permission(self):
        self.client.login(username="user_with_permission", password="password")

    def login_user_without_permission(self):
        self.client.login(username="user_without_permission", password="password")

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_access_for_user_with_permission(self):
        self.login_user_with_permission()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/page/form.html")
        self.assertIn("form", response.context)
        self.assertIsInstance(response.context["form"], PageForm)

    def test_access_for_user_without_permission(self):
        self.login_user_without_permission()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_successful_page_update(self):
        self.login_user_with_permission()
        data = {
            "title_en": "Updated Title (EN)",
            "title_uk": "Оновлена назва (UA)",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("manage_page_list"))
        self.page.refresh_from_db()
        self.assertEqual(self.page.title_en, "Updated Title (EN)")
        self.assertEqual(self.page.title_uk, "Оновлена назва (UA)")

    def test_invalid_form_submission(self):
        activate("en")
        self.login_user_with_permission()
        data = {
            "title_en": "",
            "title_uk": "",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        self.assertTrue(form.errors)
        self.assertIn("title_en", form.errors)
        self.assertEqual(form.errors["title_en"], ["This field is required."])

    def test_redirect_after_successful_update(self):
        self.login_user_with_permission()
        data = {
            "title_en": "Redirect Title (EN)",
            "title_uk": "Перенаправлена назва (UA)",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("manage_page_list"))

    def test_url_resolves_to_view(self):
        page = Page.objects.create(
            title="Resolve Test Page",
            slug="resolve-test-page",
            modified_by=self.user_with_permission,
        )
        view = resolve(f"/en/dashboard/hub/{page.slug}/edit/")
        self.assertEqual(view.func.__name__, PageUpdateView.as_view().__name__)


class PageDeleteViewTest(TestCase):
    def setUp(self):
        self.user_with_permission = self.create_user_with_permissions(
            username="user_with_permission",
            password="password",
            permissions=["delete_page", "view_page"],
        )
        self.user_without_permission = self.create_user_with_permissions(
            username="user_without_permission",
            password="password",
            permissions=[],
        )
        self.page = Page.objects.create(
            title="Test Page",
            slug="test-page",
            modified_by=self.user_with_permission,
        )
        self.url = reverse("page_delete", kwargs={"slug": self.page.slug})
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    @staticmethod
    def create_user_with_permissions(username, password, permissions):
        user = get_user_model().objects.create_user(
            username=username, password=password
        )
        for codename in permissions:
            permission = Permission.objects.get(codename=codename)
            user.user_permissions.add(permission)
        return user

    def login_user(self, username, password):
        self.client.login(username=username, password=password)

    def test_url_resolves_to_view(self):
        page = Page.objects.create(
            title="Resolve Test Page",
            slug="resolve-test-page",
            modified_by=self.user_with_permission,
        )
        activate("en")
        view = resolve(f"/en/dashboard/hub/{page.slug}/delete/")
        self.assertEqual(view.func.__name__, PageDeleteView.as_view().__name__)

    def test_access_for_user_with_permission(self):
        self.login_user("user_with_permission", "password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/page/delete.html")
        self.assertIn("object", response.context)
        self.assertEqual(response.context["object"], self.page)

    def test_access_for_user_without_permission(self):
        self.login_user("user_without_permission", "password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_successful_page_deletion(self):
        self.login_user("user_with_permission", "password")
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("manage_page_list"))
        with self.assertRaises(Page.DoesNotExist):
            Page.objects.get(slug="test-page")

    def test_invalid_access_for_unauthenticated_user(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_invalid_deletion_for_unauthenticated_user(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_delete_nonexistent_page(self):
        self.login_user("user_with_permission", "password")
        non_existent_url = reverse("page_delete", kwargs={"slug": "non-existent-slug"})
        response = self.client.post(non_existent_url)
        self.assertEqual(response.status_code, 404)

    def test_delete_confirmation_page(self):
        self.login_user("user_with_permission", "password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Are you sure you want to delete")

    def test_context_contains_correct_object(self):
        self.login_user("user_with_permission", "password")
        response = self.client.get(self.url)
        self.assertEqual(response.context["object"], self.page)

    def test_delete_page_with_different_locale(self):
        self.login_user("user_with_permission", "password")

        response_en = self.client.get(f"/en/dashboard/hub/{self.page.slug}/delete/")
        self.assertEqual(response_en.status_code, 200)

        response_uk = self.client.get(f"/uk/dashboard/hub/{self.page.slug}/delete/")
        self.assertEqual(response_uk.status_code, 200)


class SectionCreateViewTests(TestCase):
    def setUp(self):
        # Create a user with the necessary permissions
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_view_page = Permission.objects.get(codename="view_page")
        permission_view_section = Permission.objects.get(codename="view_section")
        permission_add_section = Permission.objects.get(codename="add_section")
        self.user_with_permission.user_permissions.add(
            permission_view_page, permission_view_section, permission_add_section
        )
        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )

        # Create a test page
        self.page = Page.objects.create(
            title="Test Page",
            slug="test-page",
            modified_by=self.user_with_permission,
        )

        # Set up the URL for testing
        self.url = reverse("page_section_update", kwargs={"slug": self.page.slug})
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        # Reset logging level after the test
        self.logger.setLevel(logging.DEBUG)

    def test_access_with_permission(self):
        """Test access to the page section update view with the correct permissions."""
        self.client.login(username="user_with_permission", password="password")
        self.assertTrue(
            self.user_with_permission.has_perm("hub.add_section"),
            "The user must have the hub.add_section permission.",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_access_without_permission(self):
        """Test access to the page section update view without the correct permissions."""
        self.client.login(username="user_without_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_create_section_success(self):
        """Test successful creation of a section."""
        self.client.login(username="user_with_permission", password="password")
        data = {
            "sections-0-title_draft_en": "New Section Title EN",
            "sections-0-title_draft_uk": "Новий розділ UK",
            "sections-TOTAL_FORMS": 1,
            "sections-INITIAL_FORMS": 0,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        self.assertTrue(
            Section.objects.filter(
                title_draft_en="New Section Title EN", page=self.page
            ).exists()
        )

    def test_create_section_with_empty_data(self):
        """Test section creation with empty data."""
        self.client.login(username="user_with_permission", password="password")
        data = {
            "sections-0-title_draft_en": "",
            "sections-0-title_draft_uk": "",
            "sections-TOTAL_FORMS": 1,
            "sections-INITIAL_FORMS": 0,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(
            response.status_code, 302
        )  # Expect redirect after successful save
        self.assertTrue(Section.objects.filter(page=self.page).exists())

    def test_success_url(self):
        """Test the success URL after creating a section."""
        self.client.login(username="user_with_permission", password="password")
        data = {
            "sections-0-title_draft_en": "New Section Title EN",
            "sections-0-title_draft_uk": "Новий розділ UK",
            "sections-TOTAL_FORMS": 1,
            "sections-INITIAL_FORMS": 0,
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response, reverse("page_section_update", kwargs={"slug": self.page.slug})
        )


class PageSectionUpdateViewTests(TestCase):
    def setUp(self):
        self.user_with_permission_request_update = get_user_model().objects.create_user(
            username="user_with_permission_request_update", password="password"
        )

        self.user_with_permission_confirm_update = get_user_model().objects.create_user(
            username="user_with_permission_confirm_update", password="password"
        )

        self.user_with_permission_reject_update = get_user_model().objects.create_user(
            username="user_with_permission_reject_update", password="password"
        )

        permission_view_page = Permission.objects.get(
            content_type__app_label="hub", codename="view_page"
        )
        permission_view_section = Permission.objects.get(
            content_type__app_label="hub", codename="view_section"
        )
        permission_request_update_en = Permission.objects.get(
            codename="request_update_en",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )
        permission_request_update_uk = Permission.objects.get(
            codename="request_update_uk",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )

        permission_confirm_update_en = Permission.objects.get(
            codename="confirm_update_en",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )
        permission_confirm_update_uk = Permission.objects.get(
            codename="confirm_update_uk",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )

        permission_reject_update_en = Permission.objects.get(
            codename="reject_update_en",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )

        permission_reject_update_uk = Permission.objects.get(
            codename="reject_update_uk",
            content_type=ContentType.objects.get(app_label="hub", model="section"),
        )

        self.user_with_permission_request_update.user_permissions.add(
            permission_view_page,
            permission_view_section,
            permission_request_update_en,
            permission_request_update_uk,
        )

        self.user_with_permission_confirm_update.user_permissions.add(
            permission_view_page,
            permission_view_section,
            permission_request_update_en,
            permission_request_update_uk,
            permission_confirm_update_en,
            permission_confirm_update_uk,
        )

        self.user_with_permission_reject_update.user_permissions.add(
            permission_view_page,
            permission_view_section,
            permission_request_update_en,
            permission_request_update_uk,
            permission_reject_update_en,
            permission_reject_update_uk,
        )

        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )

        self.page = Page.objects.create(
            title="Test Page",
            slug="test-page",
            modified_by=self.user_with_permission_request_update,
        )
        self.section = Section.objects.create(
            page=self.page,
            title_en="Test Section",
            title_uk="Тестовий розділ",
            title_draft_en="Draft Title EN",
            title_draft_uk="Проект назви UK",
        )

        self.url = reverse("page_section_update", kwargs={"slug": self.page.slug})
        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_access_with_permission(self):
        """Ensure user with permission can access the view."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_access_without_permission(self):
        """Ensure user without permission cannot access the view."""
        self.client.login(username="user_without_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_formset(self):
        """Ensure formset is returned correctly."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("formset", response.context)
        self.assertEqual(len(response.context["formset"].forms), 1)

    def test_request_update_en(self):
        """Test that 'request_update_en' updates 'original_data' when not set."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        # Correct POST data
        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),  # Ensure the correct prefix is used
            "sections-0-request_update_en": "on",  # Matches the expected field name
        }

        # Send POST request
        response = self.client.post(self.url, post_data)

        # Check for redirect or error
        if response.status_code == 302:
            print("Redirect occurred, response URL:", response.url)
        elif response.status_code == 200 and "formset" in response.context:
            print("Formset errors:", response.context["formset"].errors)
        else:
            self.fail(
                f"Unexpected response: status_code={response.status_code}, content={response.content}"
            )

        # Refresh the section object and check original_data
        self.section.refresh_from_db()

        self.assertIsNotNone(
            self.section.original_data,
            "original_data should not be None after update request",
        )
        self.assertIn(
            "title_draft_en",
            self.section.original_data,
            "original_data should include 'title_draft_en'",
        )

    def test_request_update_uk(self):
        """Test that 'request_update_uk' updates 'original_data' when not set."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        # Correct POST data for UK update
        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),  # Ensure the correct prefix is used
            "sections-0-request_update_uk": "on",  # Matches the expected field name
        }

        # Send POST request
        response = self.client.post(self.url, post_data)

        # Check for redirect or error
        if response.status_code == 302:
            print("Redirect occurred, response URL:", response.url)
        elif response.status_code == 200 and "formset" in response.context:
            print("Formset errors:", response.context["formset"].errors)
        else:
            self.fail(
                f"Unexpected response: status_code={response.status_code}, content={response.content}"
            )

        # Refresh the section object and check original_data
        self.section.refresh_from_db()

        self.assertIsNotNone(
            self.section.original_data,
            "original_data should not be None after update request",
        )
        self.assertIn(
            "title_draft_uk",
            self.section.original_data,
            "original_data should include 'title_draft_uk'",
        )

    def test_set_is_update_pending_en_success(self):
        """Test that 'is_update_pending_en' is set to True when the user has permission."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),
            "sections-0-request_update_en": "on",
        }

        response = self.client.post(self.url, post_data)

        self.section.refresh_from_db()
        self.assertTrue(
            self.section.is_update_pending_en,
            "is_update_pending_en should be True after request with valid permission",
        )

    def test_set_is_update_pending_uk_success(self):
        """Test that 'is_update_pending_uk' is set to True when the user has permission."""
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),
            "sections-0-request_update_uk": "on",
        }

        response = self.client.post(self.url, post_data)

        self.section.refresh_from_db()
        self.assertTrue(
            self.section.is_update_pending_uk,
            "is_update_pending_uk should be True after request with valid permission",
        )

    def test_set_is_update_pending_en_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'request_update_en' permission."""
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),
            "sections-0-request_update_en": "on",
        }

        response = self.client.post(self.url, post_data)

        self.assertEqual(
            response.status_code,
            403,
            "PermissionDenied should return a 403 status code when the user lacks permission",
        )

    def test_set_is_update_pending_uk_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'request_update_uk' permission."""
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(self.section.id),
            "sections-0-request_update_uk": "on",
        }

        response = self.client.post(self.url, post_data)

        self.assertEqual(
            response.status_code,
            403,
            "PermissionDenied should return a 403 status code when the user lacks permission",
        )

    def test_confirm_update_en(self):
        """Test that 'confirm_update_en' updates flags and calls update_section_copy."""
        page = Page.objects.create(
            title="Confirm Update Page EN",
            modified_by=self.user_with_permission_confirm_update,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_en=True,
            original_data={"title_draft_en": None, "title_draft_uk": None},
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_confirm_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-confirm_update_en": "on",
            "sections-0-title_draft_en": "Updated Title EN",
            "sections-0-title_draft_uk": "Updated Title UK",
        }

        response = self.client.post(url, post_data)

        section.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        self.assertFalse(section.is_update_pending_en)
        self.assertTrue(section.is_update_confirmed_en)

        self.assertEqual(
            section.original_data["title_draft_en"],
            "Updated Title EN",
            "The 'title_draft_en' in 'original_data' should be updated",
        )

    def test_confirm_update_en_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'confirm_update_en' permission."""
        page = Page.objects.create(
            title="Confirm Update Page EN",
            modified_by=self.user_without_permission,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_en=True,
            original_data={"title_draft_en": "Draft Title EN", "title_draft_uk": None},
            title_draft_en="Updated Title EN",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-confirm_update_en": "on",
            "sections-0-title_draft_en": "Updated Title EN",
        }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 403)  # PermissionDenied
        section.refresh_from_db()

        self.assertTrue(section.is_update_pending_en)
        self.assertFalse(section.is_update_confirmed_en)
        self.assertEqual(
            section.original_data["title_draft_en"],
            "Draft Title EN",
            "The 'original_data' should remain unchanged if permission is denied",
        )

    def test_confirm_update_uk_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'confirm_update_uk' permission."""
        page = Page.objects.create(
            title="Confirm Update Page UK",
            modified_by=self.user_without_permission,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_uk=True,
            original_data={"title_draft_en": None, "title_draft_uk": "Draft Title UK"},
            title_draft_uk="Updated Title UK",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-confirm_update_uk": "on",
            "sections-0-title_draft_uk": "Updated Title UK",
        }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 403)  # PermissionDenied
        section.refresh_from_db()

        self.assertTrue(section.is_update_pending_uk)
        self.assertFalse(section.is_update_confirmed_uk)
        self.assertEqual(
            section.original_data["title_draft_uk"],
            "Draft Title UK",
            "The 'original_data' should remain unchanged if permission is denied",
        )

    def test_confirm_update_uk(self):
        """Test that 'confirm_update_uk' updates flags and calls update_section_copy."""
        # Create minimal objects for the test
        page = Page.objects.create(
            title="Confirm Update Page UK",
            modified_by=self.user_with_permission_confirm_update,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_uk=True,
            original_data={"title_draft_en": None, "title_draft_uk": None},
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_confirm_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-confirm_update_uk": "on",
            "sections-0-title_draft_en": "Updated Title EN",
            "sections-0-title_draft_uk": "Updated Title UK",  # Focused on UK update
        }

        response = self.client.post(url, post_data)

        # Refresh the section instance to check updates
        section.refresh_from_db()

        # Assertions for response and redirection
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        # Assertions for field updates
        self.assertFalse(section.is_update_pending_uk)
        self.assertTrue(section.is_update_confirmed_uk)

        self.assertEqual(
            section.original_data["title_draft_uk"],
            "Updated Title UK",
            "The 'title_draft_uk' in 'original_data' should be updated",
        )

    def test_reject_update_en(self):
        """Test that 'reject_update_en' restores data and resets flags."""
        page = Page.objects.create(
            title="Reject Update Page EN",
            modified_by=self.user_with_permission_reject_update,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_en=True,
            is_update_confirmed_en=False,
            original_data={
                "title_draft_en": "Original Title EN",
                "title_draft_uk": "Original Title UK",
            },
            title_draft_en="Draft Title EN",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_reject_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-reject_update_en": "on",
        }

        response = self.client.post(url, post_data)

        # Refresh section data
        section.refresh_from_db()

        # Assertions for response
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        # Assertions for field restoration
        self.assertFalse(section.is_update_pending_en)
        self.assertFalse(section.is_update_confirmed_en)
        self.assertEqual(section.title_draft_en, "Original Title EN")

    def test_reject_update_uk(self):
        """Test that 'reject_update_uk' restores data and resets flags."""
        page = Page.objects.create(
            title="Reject Update Page UK",
            modified_by=self.user_with_permission_reject_update,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_uk=True,
            is_update_confirmed_uk=True,
            original_data={
                "title_draft_en": "Original Title EN",
                "title_draft_uk": "Original Title UK",
            },
            title_draft_uk="Updated Title UK",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_reject_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-reject_update_uk": "on",
        }

        response = self.client.post(url, post_data)

        # Refresh section data
        section.refresh_from_db()

        # Assertions for response
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        # Assertions for field restoration
        self.assertFalse(section.is_update_pending_uk)
        self.assertFalse(section.is_update_confirmed_uk)
        self.assertEqual(section.title_draft_uk, "Original Title UK")

    def test_reject_update_en_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'reject_update_en' permission."""
        page = Page.objects.create(
            title="Reject Update Page EN",
            modified_by=self.user_without_permission,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_en=True,
            original_data={"title_draft_en": "Draft Title EN"},
            title_draft_en="Updated Title EN",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-reject_update_en": "on",
        }

        response = self.client.post(url, post_data)

        # Check for the correct response
        self.assertEqual(response.status_code, 403)  # PermissionDenied
        section.refresh_from_db()

        # Ensure flags are not changed
        self.assertTrue(section.is_update_pending_en)
        self.assertFalse(section.is_update_confirmed_en)

        # Ensure original_data is unchanged
        self.assertEqual(
            section.original_data["title_draft_en"],
            "Draft Title EN",
            "The 'original_data' should remain unchanged if permission is denied.",
        )

    def test_reject_update_uk_permission_denied(self):
        """Test that 'PermissionDenied' is raised if the user lacks 'reject_update_uk' permission."""
        page = Page.objects.create(
            title="Reject Update Page UK",
            modified_by=self.user_without_permission,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_uk=True,
            original_data={"title_draft_uk": "Draft Title UK"},
            title_draft_uk="Updated Title UK",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(username="user_without_permission", password="password")

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-reject_update_uk": "on",
        }

        response = self.client.post(url, post_data)

        # Check for the correct response
        self.assertEqual(response.status_code, 403)  # PermissionDenied
        section.refresh_from_db()

        # Ensure flags are not changed
        self.assertTrue(section.is_update_pending_uk)
        self.assertFalse(section.is_update_confirmed_uk)

        # Ensure original_data is unchanged
        self.assertEqual(
            section.original_data["title_draft_uk"],
            "Draft Title UK",
            "The 'original_data' should remain unchanged if permission is denied.",
        )

    def test_redirect_after_post(self):
        """Test that the view redirects to 'page_section_update' after a successful POST."""
        page = Page.objects.create(
            title="Redirect Test Page",
            modified_by=self.user_with_permission_confirm_update,
        )
        section = Section.objects.create(
            page=page,
            is_update_pending_en=True,
            original_data={"title_draft_en": None, "title_draft_uk": None},
            title_draft_en="Draft Title EN",
        )

        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_confirm_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-id": str(section.id),
            "sections-0-confirm_update_en": "on",
            "sections-0-title_draft_en": "Updated Title EN",
            "sections-0-title_draft_uk": "Updated Title UK",
        }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

        section.refresh_from_db()
        self.assertFalse(section.is_update_pending_en)
        self.assertTrue(section.is_update_confirmed_en)
        self.assertEqual(
            section.original_data["title_draft_en"],
            "Updated Title EN",
            "The 'title_draft_en' in 'original_data' should be updated",
        )

    def test_render_to_response_on_get(self):
        """Test that the view renders correctly on a GET request."""
        page = Page.objects.create(
            title="Render Test Page",
            modified_by=self.user_with_permission_request_update,
        )
        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("page", response.context)
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["page"], page)
        formset_instance = response.context["formset"].instance
        self.assertEqual(formset_instance, page)

    def test_render_to_response_on_invalid_post(self):
        """Test that the view renders correctly with errors on an invalid POST request."""
        page = Page.objects.create(
            title="Render Test Page",
            modified_by=self.user_with_permission_request_update,
        )
        url = reverse("page_section_update", kwargs={"slug": page.slug})
        self.client.login(
            username="user_with_permission_request_update", password="password"
        )

        post_data = {
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "1",
        }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("formset", response.context)
        formset_errors = response.context["formset"].errors
        self.assertGreater(len(formset_errors), 0, "Formset should contain errors")


class SectionDeleteViewTests(TestCase):
    def setUp(self):
        # Create a user with delete permissions
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_view_page = Permission.objects.get(
            content_type__app_label="hub", codename="view_page"
        )
        permission_view_section = Permission.objects.get(
            content_type__app_label="hub", codename="view_section"
        )
        permission_delete_section = Permission.objects.get(
            content_type__app_label="hub", codename="delete_section"
        )
        self.user_with_permission.user_permissions.add(
            permission_view_page, permission_view_section, permission_delete_section
        )

        # Create a user without permissions
        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )

        # Create a draft section
        self.page = Page.objects.create(
            title="Test Page", slug="test-page", modified_by=self.user_with_permission
        )
        self.draft_section = Section.objects.create(
            page=self.page, title="Draft Section", status=Section.Status.DRAFT
        )

        # Create a published section
        self.published_section = Section.objects.create(
            page=self.page, title="Published Section", status=Section.Status.PUBLISHED
        )

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_user_without_permission(self):
        """Test that a user without permission cannot access the delete view."""
        self.client.login(username="user_without_permission", password="password")
        url = reverse("delete_section", kwargs={"pk": self.draft_section.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_delete_draft_section(self):
        """Test that a user with permission can delete a draft section."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("delete_section", kwargs={"pk": self.draft_section.id})
        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("page_section_update", kwargs={"slug": self.page.slug}),
        )
        with self.assertRaises(Section.DoesNotExist):
            Section.objects.get(id=self.draft_section.id)

    def test_delete_published_section(self):
        """Test that a user with permission cannot delete a published section."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("delete_section", kwargs={"pk": self.published_section.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Section.objects.filter(id=self.published_section.id).exists())

    def test_redirect_after_deletion(self):
        """Test redirection after successful deletion."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("delete_section", kwargs={"pk": self.draft_section.id})
        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("page_section_update", kwargs={"slug": self.page.slug}),
        )

    def test_correct_template_used(self):
        """Test that the correct template is used for the delete section view."""
        self.client.login(username="user_with_permission", password="password")

        url = reverse("delete_section", kwargs={"pk": self.draft_section.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/section/delete.html")

    def test_redirect_to_login_for_unauthenticated_user(self):
        """Test that unauthenticated users are redirected to the login page."""
        url = reverse("delete_section", kwargs={"pk": self.draft_section.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('account_login')}?next={url}")


class SectionPublishViewTests(TestCase):
    def setUp(self):
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_publish_section = Permission.objects.get(
            content_type__app_label="hub", codename="publish_section"
        )
        permission_view_page = Permission.objects.get(
            content_type__app_label="hub", codename="view_page"
        )
        permission_view_section = Permission.objects.get(
            content_type__app_label="hub", codename="view_section"
        )
        self.user_with_permission.user_permissions.add(
            permission_view_page, permission_view_section, permission_publish_section
        )

        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )

        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permission,
        )

        self.draft_section = Section.objects.create(
            page=self.page,
            status=Section.Status.DRAFT,
            title_draft_en="Draft Title EN",
            title_draft_uk="Draft Title UK",
            is_update_confirmed_en=True,
            is_update_confirmed_uk=True,
        )

        self.published_section = Section.objects.create(
            page=self.page,
            status=Section.Status.PUBLISHED,
        )

        self.url = reverse("publish_section", kwargs={"id": self.draft_section.id})

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_render_template_on_get(self):
        """Test that the correct template is rendered on GET requests."""
        self.client.login(username="user_with_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/section/publish.html")
        self.assertEqual(response.context["section"], self.draft_section)

    def test_redirect_unauthenticated_user(self):
        """Test that unauthenticated users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_permission_required(self):
        """Test that users without the 'publish_section' permission cannot access the view."""
        self.client.login(username="user_without_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_already_published_section(self):
        """Test that publishing an already published section shows an error message."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("publish_section", kwargs={"id": self.published_section.id})
        response = self.client.post(url)

        self.published_section.refresh_from_db()
        self.assertEqual(self.published_section.status, Section.Status.PUBLISHED)

        messages = list(response.wsgi_request._messages)
        self.assertIn(
            "This section is already published.", [str(msg) for msg in messages]
        )
        self.assertRedirects(
            response, reverse("page_section_update", kwargs={"slug": self.page.slug})
        )

    def test_updates_not_confirmed(self):
        """Test that publishing fails if updates are not confirmed."""
        self.draft_section.is_update_confirmed_en = False
        self.draft_section.is_update_confirmed_uk = True
        self.draft_section.save()

        self.client.login(username="user_with_permission", password="password")
        response = self.client.post(self.url)

        self.draft_section.refresh_from_db()
        self.assertEqual(self.draft_section.status, Section.Status.DRAFT)

        messages = list(response.wsgi_request._messages)
        self.assertIn(
            "Please confirm all content updates before publishing.",
            [str(msg) for msg in messages],
        )
        self.assertRedirects(
            response, reverse("page_section_update", kwargs={"slug": self.page.slug})
        )

    def test_successful_publishing(self):
        """Test that a draft section is successfully published."""
        self.client.login(username="user_with_permission", password="password")
        response = self.client.post(self.url)

        self.draft_section.refresh_from_db()
        self.assertEqual(self.draft_section.status, Section.Status.PUBLISHED)
        self.assertEqual(self.draft_section.title_en, "Draft Title EN")
        self.assertEqual(self.draft_section.title_uk, "Draft Title UK")
        self.assertIsNone(self.draft_section.original_data)
        self.assertFalse(self.draft_section.is_update_pending_en)
        self.assertFalse(self.draft_section.is_update_pending_uk)
        self.assertFalse(self.draft_section.is_update_confirmed_en)
        self.assertFalse(self.draft_section.is_update_confirmed_uk)

        messages = list(response.wsgi_request._messages)
        self.assertIn("Section published successfully.", [str(msg) for msg in messages])
        self.assertRedirects(
            response, reverse("page_section_update", kwargs={"slug": self.page.slug})
        )


class SectionUnpublishViewTests(TestCase):
    def setUp(self):
        self.user_with_permission = get_user_model().objects.create_user(
            username="user_with_permission", password="password"
        )
        permission_unpublish_section = Permission.objects.get(
            content_type__app_label="hub", codename="unpublish_section"
        )
        permission_view_page = Permission.objects.get(
            content_type__app_label="hub", codename="view_page"
        )
        permission_view_section = Permission.objects.get(
            content_type__app_label="hub", codename="view_section"
        )
        self.user_with_permission.user_permissions.add(
            permission_view_page, permission_view_section, permission_unpublish_section
        )

        self.user_without_permission = get_user_model().objects.create_user(
            username="user_without_permission", password="password"
        )

        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permission,
        )

        self.published_section = Section.objects.create(
            page=self.page,
            status=Section.Status.PUBLISHED,
        )

        self.draft_section = Section.objects.create(
            page=self.page,
            status=Section.Status.DRAFT,
        )

        self.url = reverse(
            "unpublish_section", kwargs={"id": self.published_section.id}
        )

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        self.logger.setLevel(logging.DEBUG)

    def test_render_template_on_get(self):
        """Test that the correct template is rendered for published sections."""
        self.client.login(username="user_with_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "hub/manage/section/unpublish.html")
        self.assertEqual(response.context["section"], self.published_section)

    def test_unpublish_non_published_section_get(self):
        """Test that a GET request for a non-published section returns 403."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("unpublish_section", kwargs={"id": self.draft_section.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_redirect_unauthenticated_user(self):
        """Test that unauthenticated users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('account_login')}?next={self.url}")

    def test_permission_required(self):
        """Test that users without the 'unpublish_section' permission cannot access the view."""
        self.client.login(username="user_without_permission", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_successful_unpublishing(self):
        """Test that a published section is successfully unpublished."""
        self.client.login(username="user_with_permission", password="password")
        response = self.client.post(self.url)

        self.published_section.refresh_from_db()
        self.assertEqual(self.published_section.status, Section.Status.DRAFT)

        self.assertRedirects(
            response, reverse("page_section_update", kwargs={"slug": self.page.slug})
        )

    def test_unpublish_non_published_section_post(self):
        """Test that a POST request for a non-published section returns 403."""
        self.client.login(username="user_with_permission", password="password")
        url = reverse("unpublish_section", kwargs={"id": self.draft_section.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class ContentCreateUpdateViewTests(TestCase):
    """
    Test case for the ContentCreateUpdateView.

    This class tests the behavior of the ContentCreateUpdateView, including
    permissions, form validation, and handling of different content types.
    """

    def setUp(self):
        """
        Set up test data, permissions, and user accounts for the tests.
        """
        # -------------------------------
        # 1. Users with and without permissions
        # -------------------------------
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # -------------------------------
        # 2. Content Types
        # -------------------------------
        # Fetch content types for each model in the app
        content_type_page = ContentType.objects.get(app_label="hub", model="page")
        content_type_section = ContentType.objects.get(app_label="hub", model="section")
        content_type_content = ContentType.objects.get(app_label="hub", model="content")

        # Content types for each content model
        content_type_text = ContentType.objects.get(app_label="hub", model="text")
        content_type_file = ContentType.objects.get(app_label="hub", model="file")
        content_type_image = ContentType.objects.get(app_label="hub", model="image")
        content_type_video = ContentType.objects.get(app_label="hub", model="video")
        content_type_url = ContentType.objects.get(app_label="hub", model="url")

        # -------------------------------
        # 3. Permissions
        # -------------------------------

        # Permissions for a Page model
        permissions_page = Permission.objects.filter(
            content_type=content_type_page,
            codename__in=[
                "view_page",
            ],
        )

        # Permissions for a Section model
        permissions_section = Permission.objects.filter(
            content_type=content_type_section,
            codename__in=[
                "request_update_en",
                "request_update_uk",
                "confirm_update_en",
                "confirm_update_uk",
                "reject_update_en",
                "reject_update_uk",
            ],
        )

        # Permissions for a Content model
        permissions_content = Permission.objects.filter(
            content_type=content_type_content,
            codename__in=[
                "view_content",
                "add_content",
                "request_update",
                "confirm_update",
                "reject_update",
            ],
        )

        # Permissions for specific content types
        permissions_text = Permission.objects.filter(
            content_type=content_type_text,
            codename__in=[
                "request_update_en",
                "request_update_uk",
                "confirm_update_en",
                "confirm_update_uk",
                "reject_update_en",
                "reject_update_uk",
            ],
        )

        permissions_other_types = Permission.objects.filter(
            content_type__in=[
                content_type_file,
                content_type_image,
                content_type_video,
                content_type_url,
            ],
            codename__in=[
                "request_update",
                "confirm_update",
                "reject_update",
            ],
        )

        # Assign all permissions to the test user
        self.user_with_permissions.user_permissions.add(
            *permissions_page,
            *permissions_section,
            *permissions_content,
            *permissions_text,
            *permissions_other_types,
        )

        # -------------------------------
        # 4. Test Data
        # -------------------------------

        # Test Page
        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permissions,
        )

        # Test Section
        self.section = Section.objects.create(
            page=self.page,
            title="Test Section",
        )

        # Models for different content types
        self.text_model = apps.get_model(app_label="hub", model_name="text")
        self.file_model = apps.get_model(app_label="hub", model_name="file")
        self.image_model = apps.get_model(app_label="hub", model_name="image")
        self.video_model = apps.get_model(app_label="hub", model_name="video")
        self.url_model = apps.get_model(app_label="hub", model_name="url")

        # -------------------------------
        # 5. Content Instances
        # -------------------------------

        # --- Mock data ---
        self.mock_file_name = "test_file.txt"
        self.mock_file = SimpleUploadedFile(
            self.mock_file_name, b"Mock file content", content_type="text/plain"
        )

        self.mock_image_name = "test_image.jpg"
        self.mock_image = SimpleUploadedFile(
            self.mock_image_name, b"Mock image content", content_type="image/jpeg"
        )

        self.mock_video_url = "https://example.com/video.mp4"
        self.mock_url = "https://example.com"

        # Text Content
        self.text_content = self.text_model.objects.create(
            title="Test Text",
            content_draft_en="Draft Text EN",
            content_draft_uk="Draft Text UK",
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.text_content)

        # File Content
        self.file_content = self.file_model.objects.create(
            title="Test File",
            content_draft=self.mock_file,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.file_content)

        image = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(image, format="JPEG")
        image.seek(0)

        # Image Content
        self.image_content = self.image_model.objects.create(
            title="Test Image",
            content_draft=self.mock_image,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.image_content)

        # Video Content
        self.video_content = self.video_model.objects.create(
            title="Test Video",
            content_draft=self.mock_video_url,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.video_content)

        # URL Content
        self.url_content = self.url_model.objects.create(
            title="Test URL",
            content_draft=self.mock_url,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.url_content)

        # -------------------------------
        # 6. URLs
        # -------------------------------
        self.create_url = reverse(
            "section_content_create",
            kwargs={"section_id": self.section.id, "model_name": "text"},
        )
        self.update_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "text",
                "id": self.text_content.id,
            },
        )

        # -------------------------------
        # 7. Template Name
        # -------------------------------
        self.template_name = "hub/manage/content/form.html"

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    def test_view_with_permission(self):
        """
        Test that a user with the 'view_content' permission can access the view.
        """
        # Log in as user with permissions
        self.client.login(username="user_with_permissions", password="password")

        # Send GET request to create URL
        response = self.client.get(self.create_url)
        self.assertEqual(
            response.status_code,
            200,
            "User with 'view_content' permission should access the view.",
        )

        # Send GET request to update URL
        response = self.client.get(self.update_url)
        self.assertEqual(
            response.status_code,
            200,
            "User with 'view_content' permission should access the update view.",
        )
        self.assertTemplateUsed(
            response,
            self.template_name,
            "The correct template should be used for content creation.",
        )

        view = ContentCreateUpdateView()

        self.assertEqual(
            view.get_model("text").__name__,
            "Text",
            "The 'get_model' method should return the 'Text' model.",
        )
        self.assertEqual(
            view.get_model("file").__name__,
            "File",
            "The 'get_model' method should return the 'File' model.",
        )
        self.assertEqual(
            view.get_model("image").__name__,
            "Image",
            "The 'get_model' method should return the 'Image' model.",
        )
        self.assertEqual(
            view.get_model("video").__name__,
            "Video",
            "The 'get_model' method should return the 'Video' model.",
        )
        self.assertEqual(
            view.get_model("url").__name__,
            "URL",
            "The 'get_model' method should return the 'URL' model.",
        )

        self.assertIsNone(
            view.get_model("invalid_model"),
            "The 'get_model' method should return None for an invalid model.",
        )

        form = view.get_form(self.text_model)
        self.assertIn(
            "content_draft_en", form.fields, "Form should include 'content_draft_en'."
        )
        self.assertIn(
            "content_draft_uk", form.fields, "Form should include 'content_draft_uk'."
        )

        form = view.get_form(self.file_model)
        self.assertIn(
            "content_draft", form.fields, "Form should include 'content_draft'."
        )

        form = view.get_form(self.image_model)
        self.assertIn(
            "content_draft", form.fields, "Form should include 'content_draft'."
        )

        form = view.get_form(self.video_model)
        self.assertIn(
            "content_draft", form.fields, "Form should include 'content_draft'."
        )

        form = view.get_form(self.url_model)
        self.assertIn(
            "content_draft", form.fields, "Form should include 'content_draft'."
        )

        """
        Update view
        """

        # Text Content (update)
        form = view.get_form(self.text_model, instance=self.text_content)
        self.assertEqual(
            form.instance.content_draft_en,
            "Draft Text EN",
            "Mock data for 'content_draft_en' should match instance data.",
        )
        self.assertEqual(
            form.instance.content_draft_uk,
            "Draft Text UK",
            "Mock data for 'content_draft_uk' should match instance data.",
        )

        # --- File Content ---
        form = view.get_form(self.file_model, instance=self.file_content)
        content_draft = form.instance.content_draft
        db_file_name = os.path.basename(content_draft.name)
        mock_file_name = self.mock_file.name

        self.assertTrue(
            db_file_name.startswith(os.path.splitext(mock_file_name)[0]),
            "Mock file base name should match instance data (ignoring suffix).",
        )

        self.assertEqual(
            os.path.splitext(db_file_name)[1],
            os.path.splitext(mock_file_name)[1],
            "File extension should match instance data.",
        )

        # --- Image Content ---
        form = view.get_form(self.image_model, instance=self.image_content)
        db_image_name = os.path.basename(form.instance.content_draft.name)
        mock_image_name = self.mock_image.name

        self.assertTrue(
            db_image_name.startswith(os.path.splitext(mock_image_name)[0]),
            "Mock file base name should match instance data (ignoring suffix).",
        )

        self.assertEqual(
            os.path.splitext(db_image_name)[1],
            os.path.splitext(mock_image_name)[1],
            "File extension should match instance data.",
        )

        # --- Video Content ---
        form = view.get_form(self.video_model, instance=self.video_content)
        self.assertEqual(
            form.instance.content_draft,
            self.mock_video_url,
            "Mock video URL should match instance data.",
        )

        # --- URL Content ---
        form = view.get_form(self.url_model, instance=self.url_content)
        self.assertEqual(
            form.instance.content_draft,
            self.mock_url,
            "Mock URL should match instance data.",
        )

    def test_view_without_permission(self):
        """
        Test that a user without the 'view_content' permission is denied access.
        """
        # Log in as user without permissions
        self.client.login(username="user_without_permissions", password="password")

        # Send GET request to create URL
        response = self.client.get(self.create_url)
        self.assertEqual(
            response.status_code,
            403,
            "User without 'view_content' permission should be denied access.",
        )

        # Send GET request to update URL
        response = self.client.get(self.update_url)
        self.assertEqual(
            response.status_code,
            403,
            "User without 'view_content' permission should be denied access to update view.",
        )

    def test_dispatch_create_permission_required(self):
        """Test that PermissionDenied is raised if a user lacks 'add_content' permission when creating."""
        self.client.login(username="user_without_permissions", password="password")
        response = self.client.post(self.create_url)
        self.assertEqual(response.status_code, 403)

    def test_dispatch_invalid_section(self):
        """Test that Http404 is raised if a section does not exist."""
        self.client.login(username="user_with_permissions", password="password")
        invalid_url = reverse(
            "section_content_create",
            kwargs={"section_id": uuid.uuid4(), "model_name": "text"},
        )
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 404)

    def test_dispatch_invalid_model_name(self):
        """Test that Http404 is raised if an invalid model name is provided."""
        self.client.login(username="user_with_permissions", password="password")
        invalid_url = reverse(
            "section_content_create",
            kwargs={"section_id": self.section.id, "model_name": "invalid_model"},
        )
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 404)

    def test_dispatch_invalid_object_id(self):
        """Test that Http404 is raised if object ID does not exist."""
        self.client.login(username="user_with_permissions", password="password")
        invalid_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "text",
                "id": uuid.uuid4(),
            },
        )
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 404)

    def test_get_create_content(self):
        """Test GET request for creating new content (empty form)."""
        self.client.login(username="user_with_permissions", password="password")

        # GET-запрос на создание нового контента
        response = self.client.get(self.create_url)

        # Проверка кода ответа
        self.assertEqual(response.status_code, 200)

        # Проверка использования шаблона
        self.assertTemplateUsed(response, self.template_name)

        # Проверка, что форма пуста
        form = response.context["form"]
        self.assertFalse(form.is_bound, "Form should be unbound for new content.")

    def test_get_update_content(self):
        """Test GET request for updating existing content (pre-filled form)."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.get(self.update_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template_name)

        form = response.context["form"]
        self.assertFalse(form.is_bound, "Form should not be bound in GET request.")
        self.assertEqual(
            form.initial.get("content_draft_en"),
            self.text_content.content_draft_en,
            "EN draft should match instance data.",
        )
        self.assertEqual(
            form.initial.get("content_draft_uk"),
            self.text_content.content_draft_uk,
            "UK draft should match instance data.",
        )

    def test_request_update_permission_denied(self):
        """Test permission denied for request update without proper permissions."""
        self.client.login(username="user_without_permissions", password="password")

        post_data = {
            "request_update": "on",
            "content_draft_en": "Updated EN",
            "content_draft_uk": "Updated UK",
        }

        response = self.client.post(self.update_url, data=post_data)
        self.assertEqual(
            response.status_code, 403, "PermissionDenied should be raised."
        )

    def test_request_update_with_permissions(self):
        """Test successful request update with proper permissions for all content types."""
        self.client.login(username="user_with_permissions", password="password")

        # --- TEXT Content ---
        post_data_text = {
            "request_update_en": "on",
            "request_update_uk": "on",
            "content_draft_en": "Updated EN",
            "content_draft_uk": "Updated UK",
        }

        response = self.client.post(self.update_url, data=post_data_text)
        self.assertEqual(
            response.status_code, 302, "Should redirect after update request."
        )

        updated_text_content = self.text_model.objects.get(id=self.text_content.id)
        self.assertTrue(updated_text_content.is_update_pending_en)
        self.assertTrue(updated_text_content.is_update_pending_uk)

        self.assertIn("content_draft_en", updated_text_content.original_data)
        self.assertIn("content_draft_uk", updated_text_content.original_data)

        # --- FILE Content ---
        post_data_file = {
            "request_update": "on",
        }

        response = self.client.post(
            reverse(
                "section_content_update",
                kwargs={
                    "section_id": self.section.id,
                    "model_name": "file",
                    "id": self.file_content.id,
                },
            ),
            data=post_data_file,
        )
        self.assertEqual(
            response.status_code, 302, "Should redirect after update request (File)."
        )

        updated_file_content = self.file_model.objects.get(id=self.file_content.id)
        self.assertTrue(updated_file_content.is_update_pending)
        self.assertIn("content_draft", updated_file_content.original_data)

        # --- IMAGE Content ---
        post_data_image = {
            "request_update": "on",
        }

        response = self.client.post(
            reverse(
                "section_content_update",
                kwargs={
                    "section_id": self.section.id,
                    "model_name": "image",
                    "id": self.image_content.id,
                },
            ),
            data=post_data_image,
        )
        self.assertEqual(
            response.status_code, 302, "Should redirect after update request (Image)."
        )

        updated_image_content = self.image_model.objects.get(id=self.image_content.id)
        self.assertTrue(updated_image_content.is_update_pending)
        self.assertIn("content_draft", updated_image_content.original_data)

        # --- VIDEO Content ---
        post_data_video = {
            "request_update": "on",
        }

        response = self.client.post(
            reverse(
                "section_content_update",
                kwargs={
                    "section_id": self.section.id,
                    "model_name": "video",
                    "id": self.video_content.id,
                },
            ),
            data=post_data_video,
        )
        self.assertEqual(
            response.status_code, 302, "Should redirect after update request (Video)."
        )

        updated_video_content = self.video_model.objects.get(id=self.video_content.id)
        self.assertTrue(updated_video_content.is_update_pending)
        self.assertIn("content_draft", updated_video_content.original_data)

        # --- URL Content ---
        post_data_url = {
            "request_update": "on",
        }

        response = self.client.post(
            reverse(
                "section_content_update",
                kwargs={
                    "section_id": self.section.id,
                    "model_name": "url",
                    "id": self.url_content.id,
                },
            ),
            data=post_data_url,
        )
        self.assertEqual(
            response.status_code, 302, "Should redirect after update request (URL)."
        )

        updated_url_content = self.url_model.objects.get(id=self.url_content.id)
        self.assertTrue(updated_url_content.is_update_pending)
        self.assertIn("content_draft", updated_url_content.original_data)

    def test_confirm_update_permission_denied(self):
        """Test permission denied for confirmation update without permissions."""
        self.client.login(username="user_without_permissions", password="password")

        post_data = {
            "confirm_update": "on",
        }

        response = self.client.post(self.update_url, data=post_data)
        self.assertEqual(
            response.status_code, 403, "PermissionDenied should be raised."
        )

    def test_confirm_update_with_permissions(self):
        """Test successfully confirm update with proper permissions for all content types."""
        self.client.login(username="user_with_permissions", password="password")

        # --- TEXT CONTENT ---
        post_data = {
            "confirm_update": "on",
            "confirm_update_en": "on",
            "confirm_update_uk": "on",
        }

        response = self.client.post(self.update_url, data=post_data)
        self.assertEqual(
            response.status_code, 302, "Should redirect after confirm update."
        )

        # Test TEXT
        updated_text_content = self.text_model.objects.get(id=self.text_content.id)

        self.assertFalse(updated_text_content.is_update_pending_en)
        self.assertFalse(updated_text_content.is_update_pending_uk)
        self.assertTrue(updated_text_content.is_update_confirmed_en)
        self.assertTrue(updated_text_content.is_update_confirmed_uk)
        self.assertIsNone(
            updated_text_content.original_data,
            "Original data should be cleared after confirmation for text.",
        )

        # --- FILE CONTENT ---
        post_data = {"confirm_update": "on"}
        file_update_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "file",
                "id": self.file_content.id,
            },
        )
        response = self.client.post(file_update_url, data=post_data)
        self.assertEqual(
            response.status_code, 302, "Should redirect after confirm update for file."
        )

        updated_file_content = self.file_model.objects.get(id=self.file_content.id)
        self.assertFalse(updated_file_content.is_update_pending)
        self.assertTrue(updated_file_content.is_update_confirmed)
        self.assertIsNone(
            updated_file_content.original_data,
            "Original data should be cleared after confirmation for file.",
        )

        # --- IMAGE CONTENT ---
        post_data = {"confirm_update": "on"}
        image_update_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "image",
                "id": self.image_content.id,
            },
        )
        response = self.client.post(image_update_url, data=post_data)
        self.assertEqual(
            response.status_code, 302, "Should redirect after confirm update for image."
        )

        updated_image_content = self.image_model.objects.get(id=self.image_content.id)
        self.assertFalse(updated_image_content.is_update_pending)
        self.assertTrue(updated_image_content.is_update_confirmed)
        self.assertIsNone(
            updated_image_content.original_data,
            "Original data should be cleared after confirmation for image.",
        )

        # --- VIDEO CONTENT ---
        post_data = {"confirm_update": "on"}
        video_update_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "video",
                "id": self.video_content.id,
            },
        )
        response = self.client.post(video_update_url, data=post_data)
        self.assertEqual(
            response.status_code, 302, "Should redirect after confirm update for video."
        )

        updated_video_content = self.video_model.objects.get(id=self.video_content.id)
        self.assertFalse(updated_video_content.is_update_pending)
        self.assertTrue(updated_video_content.is_update_confirmed)
        self.assertIsNone(
            updated_video_content.original_data,
            "Original data should be cleared after confirmation for video.",
        )

        # --- URL CONTENT ---
        post_data = {"confirm_update": "on"}
        url_update_url = reverse(
            "section_content_update",
            kwargs={
                "section_id": self.section.id,
                "model_name": "url",
                "id": self.url_content.id,
            },
        )
        response = self.client.post(url_update_url, data=post_data)
        self.assertEqual(
            response.status_code, 302, "Should redirect after confirm update for URL."
        )

        updated_url_content = self.url_model.objects.get(id=self.url_content.id)
        self.assertFalse(updated_url_content.is_update_pending)
        self.assertTrue(updated_url_content.is_update_confirmed)
        self.assertIsNone(
            updated_url_content.original_data,
            "Original data should be cleared after confirmation for URL.",
        )

    def test_reject_update_permission_denied(self):
        """Test permission denied for reject update without permissions."""
        self.client.login(username="user_without_permissions", password="password")

        post_data = {
            "reject_update": "on",
        }

        response = self.client.post(self.update_url, data=post_data)
        self.assertEqual(
            response.status_code, 403, "PermissionDenied should be raised."
        )

    def test_reject_update_with_permissions(self):
        """Test successful reject update with proper permissions for all content types."""
        self.client.login(username="user_with_permissions", password="password")

        # --- Step 1: Request update to create backup ---
        post_data_request = {
            "request_update": "on",
            "request_update_en": "on",
            "request_update_uk": "on",
            "content_draft_en": "Updated EN",
            "content_draft_uk": "Updated UK",
        }

        self.client.post(self.update_url, data=post_data_request)

        # --- Step 2: Reject update ---
        post_data_reject = {
            "reject_update": "on",
            "reject_update_en": "on",
            "reject_update_uk": "on",
        }

        response = self.client.post(self.update_url, data=post_data_reject)
        self.assertEqual(
            response.status_code, 302, "Should redirect after reject update."
        )

        # --- TEXT CONTENT ---
        updated_text_content = self.text_model.objects.get(id=self.text_content.id)

        # Assert flags are reset
        self.assertFalse(updated_text_content.is_update_pending_en)
        self.assertFalse(updated_text_content.is_update_pending_uk)

        # Check content restoration
        self.assertEqual(
            updated_text_content.content_draft_en,
            "Draft Text EN",
            "Content draft EN should be restored after reject.",
        )
        self.assertEqual(
            updated_text_content.content_draft_uk,
            "Draft Text UK",
            "Content draft UK should be restored after reject.",
        )

        # --- FILE CONTENT ---
        updated_file_content = self.file_model.objects.get(id=self.file_content.id)

        # Check flags
        self.assertFalse(updated_file_content.is_update_pending)
        self.assertFalse(updated_file_content.is_update_confirmed)

        # Extract restored file name and validate
        restored_file_name = os.path.basename(updated_file_content.content_draft.name)
        mock_file_name = self.mock_file.name

        self.assertTrue(
            restored_file_name.startswith(os.path.splitext(mock_file_name)[0]),
            "Mock file base name should match instance data (ignoring suffix).",
        )
        self.assertEqual(
            os.path.splitext(restored_file_name)[1],
            os.path.splitext(mock_file_name)[1],
            "File extension should match instance data.",
        )

        # --- IMAGE CONTENT ---
        updated_image_content = self.image_model.objects.get(id=self.image_content.id)

        # Check flags
        self.assertFalse(updated_image_content.is_update_pending)
        self.assertFalse(updated_image_content.is_update_confirmed)

        # Extract restored image name and validate
        restored_image_name = os.path.basename(updated_image_content.content_draft.name)
        mock_image_name = self.mock_image.name

        self.assertTrue(
            restored_image_name.startswith(os.path.splitext(mock_image_name)[0]),
            "Mock image base name should match instance data (ignoring suffix).",
        )
        self.assertEqual(
            os.path.splitext(restored_image_name)[1],
            os.path.splitext(mock_image_name)[1],
            "Image extension should match instance data.",
        )

        # --- VIDEO CONTENT ---
        updated_video_content = self.video_model.objects.get(id=self.video_content.id)

        # Check flags
        self.assertFalse(updated_video_content.is_update_pending)
        self.assertFalse(updated_video_content.is_update_confirmed)

        # Check restored video URL
        self.assertEqual(
            updated_video_content.content_draft,
            self.mock_video_url,
            "Video URL should be restored after reject.",
        )

        # --- URL CONTENT ---
        updated_url_content = self.url_model.objects.get(id=self.url_content.id)

        # Check flags
        self.assertFalse(updated_url_content.is_update_pending)
        self.assertFalse(updated_url_content.is_update_confirmed)

        # Check restored URL
        self.assertEqual(
            updated_url_content.content_draft,
            self.mock_url,
            "URL should be restored after reject.",
        )

    def test_post_valid_form(self):
        """Test form submission with optional fields (valid case)."""
        # Логинимся с нужными правами
        self.client.login(username="user_with_permissions", password="password")

        # Данные формы с дополнительными ключами для установки флагов
        post_data = {
            "request_update": "on",
            "request_update_en": "on",  # Добавлено для EN
            "request_update_uk": "on",  # Добавлено для UK
        }

        # Отправляем POST-запрос
        response = self.client.post(self.update_url, data=post_data)

        # Проверяем, что редирект прошел успешно
        self.assertEqual(
            response.status_code, 302, "Should redirect for valid form submission."
        )

        # Загружаем обновленный объект из базы данных
        updated_content = self.text_model.objects.get(id=self.text_content.id)

        # Проверяем, что флаг обновления установлен (логика разрешений и флагов)
        self.assertTrue(
            updated_content.is_update_pending_en,
            "Update pending EN flag should be set.",
        )
        self.assertTrue(
            updated_content.is_update_pending_uk,
            "Update pending UK flag should be set.",
        )

        # Проверяем, что оригинальные данные сохранены (если они были заданы ранее)
        self.assertIsNotNone(
            updated_content.original_data,
            "Original data should be saved for rollback.",
        )

    def test_create_content_copy(self):
        """Test creating a content copy."""
        ContentCreateUpdateView.create_content_copy(self.text_content)

        self.assertIn("content_draft_en", self.text_content.original_data)
        self.assertIn("content_draft_uk", self.text_content.original_data)

    def test_update_content_copy(self):
        """Test updating content copy."""
        ContentCreateUpdateView.create_content_copy(self.text_content)
        ContentCreateUpdateView.update_content_copy(
            self.text_content, "content_draft_en"
        )

        self.assertEqual(
            self.text_content.original_data["content_draft_en"],
            self.text_content.content_draft_en,
        )

    def test_restore_content_from_copy(self):
        """Test restoring content from copy."""
        ContentCreateUpdateView.create_content_copy(self.text_content)
        self.text_content.content_draft_en = "Modified EN"
        ContentCreateUpdateView.restore_content_from_copy(self.text_content)

        self.assertEqual(
            self.text_content.content_draft_en,
            "Draft Text EN",
            "Content should be restored from original copy.",
        )


class ContentDisplayViewTests(TestCase):
    def setUp(self):
        """Set up test data, permissions, and user accounts."""
        # Create users
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # Permissions
        content_type_content = ContentType.objects.get(app_label="hub", model="content")
        display_permission = Permission.objects.get(
            content_type=content_type_content, codename="display"
        )
        self.user_with_permissions.user_permissions.add(display_permission)

        # Test Page and Section
        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permissions,
        )
        self.section = Section.objects.create(page=self.page, title="Test Section")

        # Test Content Types
        self.text_model = apps.get_model(app_label="hub", model_name="text")
        self.file_model = apps.get_model(app_label="hub", model_name="file")

        # Mock Data
        self.mock_file = SimpleUploadedFile(
            "test_file.txt", b"Mock file content", content_type="text/plain"
        )

        # Text Content
        self.text_content = self.text_model.objects.create(
            title="Test Text",
            content_draft_en="Draft Text EN",
            content_draft_uk="Draft Text UK",
            content_en="Content EN",
            content_uk="Content UK",
            modified_by=self.user_with_permissions,
            is_update_confirmed_en=True,
            is_update_confirmed_uk=True,
        )
        self.content = Content.objects.create(
            section=self.section, item=self.text_content
        )

        # File Content
        self.file_content = self.file_model.objects.create(
            title="Test File",
            content_draft=self.mock_file,
            modified_by=self.user_with_permissions,
            is_update_confirmed=True,
        )
        self.file_content_instance = Content.objects.create(
            section=self.section, item=self.file_content
        )

        # URLs
        self.display_url = reverse(
            "section_content_display", kwargs={"id": self.content.id}
        )
        self.display_file_url = reverse(
            "section_content_display", kwargs={"id": self.file_content_instance.id}
        )

        self.template_name = "hub/manage/content/display.html"

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    # -------------------------------
    # TESTS FOR PERMISSIONS
    # -------------------------------

    def test_view_with_permission(self):
        """Test GET request with required permissions."""
        self.client.login(username="user_with_permissions", password="password")

        # Check access
        response = self.client.get(self.display_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template_name)

    def test_view_without_permission(self):
        """Test GET request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        # Check forbidden response
        response = self.client.get(self.display_url)
        self.assertEqual(response.status_code, 403)

    # -------------------------------
    # TESTS FOR GET REQUEST
    # -------------------------------

    def test_get_display_page(self):
        """Test GET request to display content."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.get(self.display_url)

        # Template and context check
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, self.template_name)
        self.assertIn("content", response.context)

    # -------------------------------
    # TESTS FOR POST REQUESTS
    # -------------------------------

    def test_post_valid_display_text_content(self):
        """Test POST request to display text content after confirmation."""
        self.client.login(username="user_with_permissions", password="password")

        # POST request
        response = self.client.post(self.display_url)

        # Redirect check
        self.assertEqual(response.status_code, 302)

        # Check updated text content
        updated_content = self.text_model.objects.get(id=self.text_content.id)

        self.assertEqual(updated_content.content_en, "Draft Text EN")
        self.assertEqual(updated_content.content_uk, "Draft Text UK")
        self.assertIsNone(updated_content.original_data)

    def test_post_valid_display_file_content(self):
        """Test POST request to display file content after confirmation."""
        self.client.login(username="user_with_permissions", password="password")

        post_data_confirm = {"confirm_update": "on"}
        self.client.post(self.display_file_url, data=post_data_confirm)

        post_data_display = {}
        response = self.client.post(self.display_file_url, data=post_data_display)

        self.assertEqual(
            response.status_code, 302, "Should redirect after displaying file content."
        )

        if not self.file_model.objects.filter(id=self.file_content.id).exists():
            self.fail("File content instance was deleted during the test!")

        updated_file_content = self.file_model.objects.get(id=self.file_content.id)

        self.assertFalse(updated_file_content.is_update_pending)
        self.assertFalse(updated_file_content.is_update_confirmed)

        restored_file_name = os.path.basename(updated_file_content.content.name)
        mock_file_name = os.path.basename(self.mock_file.name)

        self.assertTrue(
            restored_file_name.startswith(os.path.splitext(mock_file_name)[0]),
            "Restored file base name should match the mock file.",
        )

        self.assertEqual(
            os.path.splitext(restored_file_name)[1],
            os.path.splitext(mock_file_name)[1],
            "File extension should match the mock file.",
        )

        content_instance = Content.objects.get(object_id=self.file_content.id)
        self.assertEqual(
            content_instance.status,
            Content.Status.DISPLAY,
            "Content should be displayed.",
        )

    def test_post_invalid_display_text_content(self):
        """Test POST request with unconfirmed text content."""
        self.client.login(username="user_with_permissions", password="password")

        self.text_content.is_update_confirmed_en = False
        self.text_content.is_update_confirmed_uk = False
        self.text_content.save()

        post_data_display = {}
        response = self.client.post(self.display_url, data=post_data_display)

        self.assertEqual(
            response.status_code, 302, "Should redirect after invalid display request."
        )

        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))

        self.assertTrue(
            any(
                "Please confirm all content updates (EN and UK) before displaying."
                in str(message)
                for message in messages
            ),
            "Should display error message for unconfirmed content.",
        )

        content_instance = Content.objects.get(id=self.content.id)
        self.assertNotEqual(
            content_instance.status,
            Content.Status.DISPLAY,
            "Content should not be displayed when updates are unconfirmed.",
        )

    def test_post_invalid_display_file_content(self):
        """Test POST request with unconfirmed file content."""
        self.client.login(username="user_with_permissions", password="password")

        # Unconfirmed updates
        self.file_content.is_update_confirmed = False
        self.file_content.save()

        # POST request
        response = self.client.post(self.display_file_url)

        # Redirect and error message check
        self.assertEqual(response.status_code, 302)

        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))
        self.assertIn(
            "Please confirm all content updates before displaying.",
            [str(msg) for msg in messages],
        )


class ContentHideViewTests(TestCase):
    """Test suite for ContentHideView."""

    def setUp(self):
        """Set up test data, users, permissions, and mock content."""
        # -------------------------------
        # Users
        # -------------------------------
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # Permissions
        content_type_content = ContentType.objects.get(app_label="hub", model="content")
        hide_permission = Permission.objects.get(
            content_type=content_type_content, codename="hide"
        )
        self.user_with_permissions.user_permissions.add(hide_permission)

        # -------------------------------
        # Page and Section
        # -------------------------------
        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permissions,
        )
        self.section = Section.objects.create(page=self.page, title="Test Section")

        # -------------------------------
        # Content Models
        # -------------------------------
        self.text_model = apps.get_model(app_label="hub", model_name="text")
        self.file_model = apps.get_model(app_label="hub", model_name="file")

        # Mock Data
        self.mock_file = SimpleUploadedFile(
            "test_file.txt", b"Mock file content", content_type="text/plain"
        )

        # Text Content
        self.text_content = self.text_model.objects.create(
            title="Test Text",
            content_draft_en="Draft Text EN",
            content_draft_uk="Draft Text UK",
            content_en="Content EN",
            content_uk="Content UK",
            modified_by=self.user_with_permissions,
            is_update_confirmed_en=True,
            is_update_confirmed_uk=True,
        )
        self.text_content_instance = Content.objects.create(
            section=self.section, item=self.text_content, status=Content.Status.DISPLAY
        )

        # File Content
        self.file_content = self.file_model.objects.create(
            title="Test File",
            content_draft=self.mock_file,
            modified_by=self.user_with_permissions,
            is_update_confirmed=True,
        )
        self.file_content_instance = Content.objects.create(
            section=self.section, item=self.file_content, status=Content.Status.DISPLAY
        )

        # -------------------------------
        # URLs
        # -------------------------------
        self.hide_url_text = reverse(
            "section_content_hide", kwargs={"id": self.text_content_instance.id}
        )
        self.hide_url_file = reverse(
            "section_content_hide", kwargs={"id": self.file_content_instance.id}
        )

        # Template name
        self.template_name = "hub/manage/content/hide.html"

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    # -----------------------------------------
    # 1. Permissions and Template Tests
    # -----------------------------------------
    def test_view_with_permission(self):
        """Test GET request with required permissions."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.get(self.hide_url_text)
        self.assertEqual(
            response.status_code, 200, "Should return 200 for GET request."
        )
        self.assertTemplateUsed(response, self.template_name)

        # Context contains content object
        self.assertIn("content", response.context, "Context should include 'content'.")

    def test_view_without_permission(self):
        """Test GET request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        response = self.client.get(self.hide_url_text)
        self.assertEqual(
            response.status_code, 403, "Should return 403 without permission."
        )

    # -----------------------------------------
    # 2. Valid POST - Hide Text Content
    # -----------------------------------------
    def test_post_valid_hide_text_content(self):
        """Test POST request to hide text content after confirmation."""
        self.client.login(username="user_with_permissions", password="password")

        post_data = {}
        response = self.client.post(self.hide_url_text, data=post_data)

        # Redirect check
        self.assertEqual(
            response.status_code, 302, "Should redirect after successful hide."
        )

        # Status check
        updated_text_content = Content.objects.get(id=self.text_content_instance.id)
        self.assertEqual(
            updated_text_content.status,
            Content.Status.HIDE,
            "Text content should be hidden.",
        )

        # Flags check
        self.assertFalse(updated_text_content.item.is_update_pending_en)
        self.assertFalse(updated_text_content.item.is_update_pending_uk)
        self.assertFalse(updated_text_content.item.is_update_confirmed_en)
        self.assertFalse(updated_text_content.item.is_update_confirmed_uk)

        # Messages check
        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any("Content hidden successfully." in str(m) for m in messages),
            "Should display success message.",
        )

    # -----------------------------------------
    # 3. Valid POST - Hide File Content
    # -----------------------------------------
    def test_post_valid_hide_file_content(self):
        """Test POST request to hide file content after confirmation."""
        self.client.login(username="user_with_permissions", password="password")

        post_data = {}
        response = self.client.post(self.hide_url_file, data=post_data)

        # Redirect check
        self.assertEqual(
            response.status_code, 302, "Should redirect after successful hide."
        )

        # Status check
        updated_file_content = Content.objects.get(id=self.file_content_instance.id)
        self.assertEqual(
            updated_file_content.status,
            Content.Status.HIDE,
            "File content should be hidden.",
        )

        # Flags check
        self.assertFalse(updated_file_content.item.is_update_pending)
        self.assertFalse(updated_file_content.item.is_update_confirmed)

        # Messages check
        from django.contrib.messages import get_messages

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any("Content hidden successfully." in str(m) for m in messages),
            "Should display success message.",
        )

    # -----------------------------------------
    # 4. POST without Permissions
    # -----------------------------------------
    def test_post_without_permission(self):
        """Test POST request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        post_data = {}
        response = self.client.post(self.hide_url_text, data=post_data)

        # Permission check
        self.assertEqual(
            response.status_code, 403, "Should return 403 without permission."
        )

    # -----------------------------------------
    # 5. Invalid Content ID
    # -----------------------------------------
    def test_invalid_content_id(self):
        """Test request with invalid content ID."""
        self.client.login(username="user_with_permissions", password="password")

        invalid_url = reverse(
            "section_content_hide",
            kwargs={"id": "00000000-0000-0000-0000-000000000000"},
        )

        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 404, "Should return 404 for invalid ID.")

        response = self.client.post(invalid_url)
        self.assertEqual(response.status_code, 404, "Should return 404 for invalid ID.")


class ContentDeleteViewTests(TestCase):
    """Test suite for ContentDeleteView."""

    def setUp(self):
        """Set up test data, permissions, users, and mock content."""
        # -------------------------------
        # Users
        # -------------------------------
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # Permissions
        content_type_content = ContentType.objects.get(app_label="hub", model="content")
        delete_permission = Permission.objects.get(
            content_type=content_type_content, codename="delete_content"
        )
        self.user_with_permissions.user_permissions.add(delete_permission)

        # -------------------------------
        # Page and Section
        # -------------------------------
        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permissions,
        )
        self.section = Section.objects.create(page=self.page, title="Test Section")

        # -------------------------------
        # Content Models
        # -------------------------------
        self.text_model = apps.get_model(app_label="hub", model_name="text")
        self.file_model = apps.get_model(app_label="hub", model_name="file")

        # Mock Data
        self.mock_file = SimpleUploadedFile(
            "test_file.txt", b"Mock file content", content_type="text/plain"
        )

        # Text Content
        self.text_content = self.text_model.objects.create(
            title="Test Text",
            content_draft_en="Draft Text EN",
            content_draft_uk="Draft Text UK",
            content_en="Content EN",
            content_uk="Content UK",
            modified_by=self.user_with_permissions,
        )
        self.text_content_instance = Content.objects.create(
            section=self.section, item=self.text_content
        )

        # File Content
        self.file_content = self.file_model.objects.create(
            title="Test File",
            content_draft=self.mock_file,
            modified_by=self.user_with_permissions,
        )
        self.file_content_instance = Content.objects.create(
            section=self.section, item=self.file_content
        )

        # -------------------------------
        # URLs
        # -------------------------------
        self.delete_url_text = reverse(
            "section_content_delete", kwargs={"id": self.text_content_instance.id}
        )
        self.delete_url_file = reverse(
            "section_content_delete", kwargs={"id": self.file_content_instance.id}
        )

        # Template name
        self.template_name = "hub/manage/content/delete.html"

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    # -----------------------------------------
    # 1. Permissions and Template Tests
    # -----------------------------------------
    def test_view_with_permission(self):
        """Test GET request with required permissions."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.get(self.delete_url_text)
        self.assertEqual(
            response.status_code, 200, "Should return 200 for GET request."
        )
        self.assertTemplateUsed(response, self.template_name)

        # Context should include a content object
        self.assertIn("content", response.context, "Context should include 'content'.")

    def test_view_without_permission(self):
        """Test GET request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        response = self.client.get(self.delete_url_text)
        self.assertEqual(
            response.status_code, 403, "Should return 403 without permission."
        )

    # -----------------------------------------
    # 2. Valid POST - Delete Text Content
    # -----------------------------------------
    def test_post_valid_delete_text_content(self):
        """Test POST request to delete text content."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.post(self.delete_url_text)

        # Redirect check
        self.assertEqual(
            response.status_code, 302, "Should redirect after successful delete."
        )

        # Database check
        with self.assertRaises(Content.DoesNotExist):
            Content.objects.get(id=self.text_content_instance.id)

        with self.assertRaises(self.text_model.DoesNotExist):
            self.text_model.objects.get(id=self.text_content.id)

    # -----------------------------------------
    # 3. Valid POST - Delete File Content
    # -----------------------------------------
    def test_post_valid_delete_file_content(self):
        """Test POST request to delete file content."""
        self.client.login(username="user_with_permissions", password="password")

        # File existence check before deletion
        self.assertTrue(
            os.path.exists(self.file_content.content_draft.path),
            "File should exist before deletion.",
        )

        response = self.client.post(self.delete_url_file)

        # Redirect check
        self.assertEqual(
            response.status_code, 302, "Should redirect after successful delete."
        )

        # Database check
        with self.assertRaises(Content.DoesNotExist):
            Content.objects.get(id=self.file_content_instance.id)

        with self.assertRaises(self.file_model.DoesNotExist):
            self.file_model.objects.get(id=self.file_content.id)

        # File should be deleted from storage
        self.assertFalse(
            os.path.exists(self.file_content.content_draft.path),
            "File should be deleted from storage.",
        )

    # -----------------------------------------
    # 4. POST without Permissions
    # -----------------------------------------
    def test_post_without_permission(self):
        """Test POST request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        response = self.client.post(self.delete_url_text)
        self.assertEqual(
            response.status_code, 403, "Should return 403 without permission."
        )

    # -----------------------------------------
    # 5. Invalid Content ID
    # -----------------------------------------
    def test_invalid_content_id(self):
        """Test request with invalid content ID."""
        self.client.login(username="user_with_permissions", password="password")

        invalid_url = reverse(
            "section_content_delete",
            kwargs={"id": "00000000-0000-0000-0000-000000000000"},
        )

        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 404, "Should return 404 for invalid ID.")

        response = self.client.post(invalid_url)
        self.assertEqual(response.status_code, 404, "Should return 404 for invalid ID.")


class SectionContentListViewTests(TestCase):
    """Test suite for SectionContentListView with extended setup."""

    def setUp(self):
        """Set up test data, permissions, and user accounts."""
        # -------------------------------
        # 1. Users
        # -------------------------------
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # -------------------------------
        # 2. Content Types
        # -------------------------------
        content_type_page = ContentType.objects.get(app_label="hub", model="page")
        content_type_section = ContentType.objects.get(app_label="hub", model="section")
        content_type_content = ContentType.objects.get(app_label="hub", model="content")

        # Content models
        content_type_text = ContentType.objects.get(app_label="hub", model="text")
        content_type_file = ContentType.objects.get(app_label="hub", model="file")
        content_type_image = ContentType.objects.get(app_label="hub", model="image")
        content_type_video = ContentType.objects.get(app_label="hub", model="video")
        content_type_url = ContentType.objects.get(app_label="hub", model="url")

        # -------------------------------
        # 3. Permissions
        # -------------------------------
        # Permissions for a Page model
        permissions_page = Permission.objects.filter(
            content_type=content_type_page,
            codename__in=[
                "view_page",
            ],
        )

        # Permissions for a Section model
        permissions_section = Permission.objects.filter(
            content_type=content_type_section,
            codename__in=[
                "request_update_en",
                "request_update_uk",
                "confirm_update_en",
                "confirm_update_uk",
                "reject_update_en",
                "reject_update_uk",
            ],
        )

        # Permissions for a Content model
        permissions_content = Permission.objects.filter(
            content_type=content_type_content,
            codename__in=[
                "view_content",
                "add_content",
                "request_update",
                "confirm_update",
                "reject_update",
            ],
        )

        # Permissions for specific content types
        permissions_text = Permission.objects.filter(
            content_type=content_type_text,
            codename__in=[
                "request_update_en",
                "request_update_uk",
                "confirm_update_en",
                "confirm_update_uk",
                "reject_update_en",
                "reject_update_uk",
            ],
        )

        permissions_other_types = Permission.objects.filter(
            content_type__in=[
                content_type_file,
                content_type_image,
                content_type_video,
                content_type_url,
            ],
            codename__in=[
                "request_update",
                "confirm_update",
                "reject_update",
            ],
        )

        # Assign all permissions to the test user
        self.user_with_permissions.user_permissions.add(
            *permissions_page,
            *permissions_section,
            *permissions_content,
            *permissions_text,
            *permissions_other_types,
        )

        # -------------------------------
        # 4. Test Page and Section
        # -------------------------------
        # Test Page
        self.page = Page.objects.create(
            title="Test Page",
            modified_by=self.user_with_permissions,
        )

        # Test Section
        self.section = Section.objects.create(
            page=self.page,
            title="Test Section",
        )

        # Models for different content types
        self.text_model = apps.get_model(app_label="hub", model_name="text")
        self.file_model = apps.get_model(app_label="hub", model_name="file")
        self.image_model = apps.get_model(app_label="hub", model_name="image")
        self.video_model = apps.get_model(app_label="hub", model_name="video")
        self.url_model = apps.get_model(app_label="hub", model_name="url")

        # -------------------------------
        # 5. Mock Data for Content Types
        # -------------------------------
        self.mock_file_name = "test_file.txt"
        self.mock_file = SimpleUploadedFile(
            self.mock_file_name, b"Mock file content", content_type="text/plain"
        )

        self.mock_image_name = "test_image.jpg"
        self.mock_image = SimpleUploadedFile(
            self.mock_image_name, b"Mock image content", content_type="image/jpeg"
        )

        self.mock_video_url = "https://example.com/video.mp4"
        self.mock_url = "https://example.com"

        # Text Content
        self.text_content = self.text_model.objects.create(
            title="Test Text",
            content_draft_en="Draft Text EN",
            content_draft_uk="Draft Text UK",
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.text_content)

        # File Content
        self.file_content = self.file_model.objects.create(
            title="Test File",
            content_draft=self.mock_file,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.file_content)

        image = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(image, format="JPEG")
        image.seek(0)

        # Image Content
        self.image_content = self.image_model.objects.create(
            title="Test Image",
            content_draft=self.mock_image,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.image_content)

        # Video Content
        self.video_content = self.video_model.objects.create(
            title="Test Video",
            content_draft=self.mock_video_url,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.video_content)

        # URL Content
        self.url_content = self.url_model.objects.create(
            title="Test URL",
            content_draft=self.mock_url,
            modified_by=self.user_with_permissions,
        )
        Content.objects.create(section=self.section, item=self.url_content)

        # -------------------------------
        # 6. URLs
        # -------------------------------
        self.list_url = reverse(
            "section_content_list", kwargs={"section_id": self.section.id}
        )

        # -------------------------------
        # 8. Template
        # -------------------------------
        self.template_name = "hub/manage/section/content_list.html"

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    # -----------------------------------------
    # Test Cases
    # -----------------------------------------

    def test_view_with_permission(self):
        """Test GET request with required permissions."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.get(self.list_url)

        # Response and template checks
        self.assertEqual(
            response.status_code, 200, "Should return 200 for GET request."
        )
        self.assertTemplateUsed(
            response,
            self.template_name,
            "Should use the correct template for content list.",
        )

        # Context check
        self.assertIn(
            "section", response.context, "Context should include 'section' object."
        )
        self.assertEqual(
            response.context["section"].id,
            self.section.id,
            "Section in context should match the requested section.",
        )

    def test_view_without_permission(self):
        """Test GET request without required permissions."""
        self.client.login(username="user_without_permissions", password="password")

        response = self.client.get(self.list_url)

        # Permission check
        self.assertEqual(
            response.status_code, 403, "Should return 403 without proper permissions."
        )

    def test_invalid_section_id(self):
        """Test GET request with an invalid section ID."""
        self.client.login(username="user_with_permissions", password="password")

        invalid_url = reverse(
            "section_content_list",
            kwargs={"section_id": "00000000-0000-0000-0000-000000000000"},
        )

        response = self.client.get(invalid_url)

        # Invalid ID check
        self.assertEqual(
            response.status_code, 404, "Should return 404 for an invalid section ID."
        )

    def test_unauthenticated_access(self):
        """Test GET request without login."""
        response = self.client.get(self.list_url)

        # Redirect to log in
        self.assertEqual(response.status_code, 302, "Should redirect to login page.")

        # Verify redirect URL contains 'login'
        self.assertIn(
            reverse("account_login"),
            response.url,
            "Redirect should lead to login page.",
        )

    def test_section_with_content(self):
        """Test section with all content types."""
        self.client.login(username="user_with_permissions", password="password")
        response = self.client.get(self.list_url)

        # Ensure all content types exist in the section
        self.assertEqual(
            len(response.context["section"].contents.all()),
            5,
            "Section should have 5 content items.",
        )

    def test_correct_template_used(self):
        """Test that the correct template is used for rendering."""
        self.client.login(username="user_with_permissions", password="password")
        response = self.client.get(self.list_url)

        # Check that the correct template is used
        self.assertTemplateUsed(
            response,
            self.template_name,
            "View should render the correct template.",
        )

    def test_url_resolution(self):
        """Test URL resolution for the section content list."""
        # Reverse lookup for the URL
        resolved_url = reverse(
            "section_content_list", kwargs={"section_id": self.section.id}
        )
        # Assert that the resolved URL matches the expected path
        self.assertEqual(
            resolved_url,
            f"/en/dashboard/hub/section/{self.section.id}/",
            "URL resolution should match the expected path.",
        )


class SectionOrderViewTests(TestCase):
    def setUp(self):
        """Set up test data, permissions, and users."""
        # Create users
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        # Permissions
        content_type_section = ContentType.objects.get(app_label="hub", model="section")
        permission = Permission.objects.get(
            content_type=content_type_section, codename="change_section_order"
        )
        self.user_with_permissions.user_permissions.add(permission)

        # Test Page and Sections
        self.page = Page.objects.create(
            title="Test Page", modified_by=self.user_with_permissions
        )
        self.section1 = Section.objects.create(
            page=self.page, title="Section 1", order=1
        )
        self.section2 = Section.objects.create(
            page=self.page, title="Section 2", order=2
        )

        # URLs
        self.url = reverse("section_order")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    def test_authorized_user_can_update_order(self):
        """Test that an authorized user can successfully update section order."""
        self.client.login(username="user_with_permissions", password="password")

        # --- Prepare valid JSON data ---
        data = {
            str(self.section1.id): 2,  # UUID for the first section
            str(self.section2.id): 1,  # UUID for the second section
        }

        # --- Send POST request ---
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        # --- Assert Response ---
        self.assertEqual(response.status_code, 200)

        # Check database updates
        self.section1.refresh_from_db()
        self.section2.refresh_from_db()

        self.assertEqual(self.section1.order, 2)
        self.assertEqual(self.section2.order, 1)

    def test_unauthorized_user_cannot_update_order(self):
        """Test that an unauthorized user cannot update section order."""
        self.client.login(username="user_without_permissions", password="password")

        data = {
            str(self.section1.id): 2,  # UUID for the first section
            str(self.section2.id): 1,  # UUID for the second section
        }
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        # Check response status
        self.assertEqual(response.status_code, 403)

        # Ensure order remains unchanged
        self.section1.refresh_from_db()
        self.section2.refresh_from_db()
        self.assertEqual(self.section1.order, 1)
        self.assertEqual(self.section2.order, 2)

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that an unauthenticated user receives a 403 JSON response."""
        # Prepare data
        data = {str(self.section1.id): 2, str(self.section2.id): 1}

        # Send POST request without authentication
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)

        response_data = json.loads(response.content)

        self.assertIn("error", response_data)
        self.assertEqual(
            response_data["error"],
            "You do not have permission to change the section order.",
        )

    def test_invalid_data_empty_request(self):
        """Test that an empty request does not update order."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.post(self.url, {}, content_type="application/json")

        self.assertEqual(response.status_code, 400)  # Expect bad request

    def test_invalid_section_id(self):
        """Test invalid section ID in the data."""
        # Логинимся как пользователь с правами
        self.client.login(username="user_with_permissions", password="password")

        # Отправляем некорректный ID
        data = {"invalid-uuid": 1}

        # POST-запрос с некорректными данными
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        # Проверка кода состояния ответа
        self.assertEqual(response.status_code, 400)

        # Проверка сообщения об ошибке
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Invalid section ID provided.")

    def test_partial_update(self):
        """Test partial updates where only one section order is changed."""
        # Логинимся как пользователь с правами
        self.client.login(username="user_with_permissions", password="password")

        # Данные для частичного обновления
        data = {
            str(self.section1.id): 2,  # Изменяем порядок первой секции
            str(self.section2.id): 1,  # Указываем текущий порядок второй секции
        }

        # Отправляем запрос
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        # Проверка кода состояния ответа
        self.assertEqual(response.status_code, 200)

        # Обновляем данные секций из БД
        self.section1.refresh_from_db()
        self.section2.refresh_from_db()

        # Проверяем, что порядок обновился корректно
        self.assertEqual(self.section1.order, 2)  # Порядок изменился
        self.assertEqual(self.section2.order, 1)  # Порядок не изменился

        # Проверяем содержимое ответа
        response_data = json.loads(response.content)
        self.assertIn("updated", response_data)
        self.assertEqual(
            set(response_data["updated"]),  # Проверяем ID обновлённых секций
            {str(self.section1.id), str(self.section2.id)},
        )


class ContentOrderViewTests(TestCase):
    def setUp(self):
        """Set up test data, permissions, and users."""
        self.user_with_permissions = get_user_model().objects.create_user(
            username="user_with_permissions", password="password"
        )
        self.user_without_permissions = get_user_model().objects.create_user(
            username="user_without_permissions", password="password"
        )

        content_type_content = ContentType.objects.get(app_label="hub", model="content")
        permission = Permission.objects.get(
            content_type=content_type_content, codename="change_content_order"
        )
        self.user_with_permissions.user_permissions.add(permission)

        self.page = Page.objects.create(
            title="Test Page", modified_by=self.user_with_permissions
        )
        self.section = Section.objects.create(page=self.page, title="Test Section")

        content_type = ContentType.objects.get_for_model(self.page)

        self.content1 = Content.objects.create(
            content_type=content_type,
            object_id=self.page.id,
            section=self.section,
            order=1,
        )

        self.content2 = Content.objects.create(
            content_type=content_type,
            object_id=self.page.id,
            section=self.section,
            order=2,
        )

        self.url = reverse("content_order")

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    def test_authorized_user_can_update_order(self):
        """Test: An authorised user can change the order of content."""
        self.client.login(username="user_with_permissions", password="password")

        data = {
            str(self.content1.id): 2,
            str(self.content2.id): 1,
        }

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        self.content1.refresh_from_db()
        self.content2.refresh_from_db()
        self.assertEqual(self.content1.order, 2)
        self.assertEqual(self.content2.order, 1)

    def test_unauthorized_user_cannot_update_order(self):
        """Test: unauthorised user cannot change the order."""
        self.client.login(username="user_without_permissions", password="password")

        data = {
            str(self.content1.id): 2,
            str(self.content2.id): 1,
        }
        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)

        self.content1.refresh_from_db()
        self.content2.refresh_from_db()
        self.assertEqual(self.content1.order, 1)
        self.assertEqual(self.content2.order, 2)

    def test_unauthenticated_user_redirected_to_login(self):
        """Test: unauthorised user receives a 403 JSON response."""
        data = {str(self.content1.id): 2, str(self.content2.id): 1}

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)

        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(
            response_data["error"],
            "You do not have permission to change the content order.",
        )

    def test_invalid_data_empty_request(self):
        """Test: empty request returns a 400 error."""
        self.client.login(username="user_with_permissions", password="password")

        response = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_content_id(self):
        """Test: invalid content ID returns a 400 error."""
        self.client.login(username="user_with_permissions", password="password")

        data = {"invalid-uuid": 1}

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"], "Invalid content ID provided.")

    def test_partial_update(self):
        """Test: partial update of content order."""
        self.client.login(username="user_with_permissions", password="password")

        data = {
            str(self.content1.id): 2,
            str(self.content2.id): 1,
        }

        response = self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        self.content1.refresh_from_db()
        self.content2.refresh_from_db()
        self.assertEqual(self.content1.order, 2)
        self.assertEqual(self.content2.order, 1)

        response_data = json.loads(response.content)
        self.assertIn("updated", response_data)
        self.assertEqual(
            set(response_data["updated"]),
            {str(self.content1.id), str(self.content2.id)},
        )


class GlobalSearchViewTests(TestCase):
    """Tests for the global_search view."""

    def setUp(self):
        """Set up test data."""
        self.url = reverse("global_search")
        self.user = get_user_model().objects.create_user(
            username="testuser", password="password"
        )
        self.owner = get_user_model().objects.create_user(
            username="owneruser", password="password", role="OWR"
        )

        # Create sample data
        self.page = Page.objects.create(title="Test Page")
        self.section = Section.objects.create(page=self.page, title_en="Test Section")
        self.text = Text.objects.create(
            title="Sample Text",
            content_en="Example content for testing purposes.",
        )
        self.file = File.objects.create(title="Sample File")
        self.image = ImageModel.objects.create(title="Sample Image")
        self.video = Video.objects.create(title="Sample Video")
        self.url = URL.objects.create(title="Sample URL")
        self.division = Division.objects.create(
            title_en="Division 1", title_uk="Розділ 1"
        )
        self.branch = Branch.objects.create(
            title_en="Branch 1",
            address_en="Address 1",
            division=self.division,
        )
        self.person = Person.objects.create(first_name_en="John", last_name_en="Doe")
        self.donor = Donor.objects.create(
            first_name="Jane", last_name="Doe", email="jane.doe@example.com"
        )
        self.donation = Donation.objects.create(
            transaction_id="TRANS123", amount=100.0, donor=self.donor
        )

        self.logger = logging.getLogger("django.request")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Tear down any additional test data if necessary.
        """
        self.logger.setLevel(logging.DEBUG)

    def test_login_required_redirect(self):
        """Test that unauthenticated users are redirected to the login page."""
        url = reverse("global_search")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_search_no_query(self):
        """Test search without a query parameter returns no results."""
        self.client.login(username="testuser", password="password")

        url = reverse("global_search")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found.")
        self.assertEqual(len(response.context["results"]), 0)

    def test_search_with_query(self):
        """Test search with a query parameter returns relevant results."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Test"})
        self.assertEqual(response.status_code, 200)

        # Check that expected results are in context
        results = response.context["results"]
        self.assertIn(self.page, results)
        self.assertIn(self.section, results)
        self.assertNotIn(self.donor, results)

    def test_search_for_owner_role(self):
        """Test that owner role can see donors and donations."""
        self.client.login(username="owneruser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Jane"})
        self.assertEqual(response.status_code, 200)

        results = response.context["results"]
        self.assertIn(self.donor, results)
        self.assertNotIn(
            self.page, results
        )  # Testing that non-relevant results are excluded.

    def test_partial_match_query(self):
        """Test that partial matches return results."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Exampl"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertIn(self.text, results)

    def test_no_results(self):
        """Test search with no matching results."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "NonExistent"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["results"]), 0)

    def test_search_with_special_characters(self):
        """Test search handles special characters gracefully."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "!@#$%^&*()"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["results"]), 0)

    def test_case_insensitive_search(self):
        """Test that search is case-insensitive."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "test section"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertIn(self.section, results)

    def test_search_multiple_models(self):
        """Test that the search returns results from multiple models."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Sample"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]

        # Check that results span multiple models
        self.assertIn(self.text, results)
        self.assertIn(self.file, results)
        self.assertIn(self.image, results)
        self.assertIn(self.video, results)

    def test_search_donor_access(self):
        """Test that non-owners cannot access donor data."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Jane"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertNotIn(
            self.donor, results
        )  # Donor should be excluded for non-owner users.

    def test_owner_can_access_donors(self):
        """Test that owners can access donor and donation data."""
        self.client.login(username="owneruser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": "Jane"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertIn(self.donor, results)  # Owner should see donor data.

    def test_invalid_query_param(self):
        """Test that invalid query parameter does not cause errors."""
        self.client.login(username="testuser", password="password")
        url = reverse("global_search")
        response = self.client.get(url, {"query": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["results"]), 0)
