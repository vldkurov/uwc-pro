import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse, resolve
from django.utils.translation import activate

from accounts.models import CustomUser
from .forms import PageForm
from .models import Page
from .views import (
    DashboardView,
    ManagePageListView,
    PageUpdateView,
    PageCreateView,
    PageDeleteView,
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
        view = resolve("/en/hub/create/")
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
        view = resolve(f"/en/hub/{page.slug}/edit/")
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
        activate("en")  # Активируем английскую локаль
        view = resolve(f"/en/hub/{page.slug}/delete/")
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

        response_en = self.client.get(f"/en/hub/{self.page.slug}/delete/")
        self.assertEqual(response_en.status_code, 200)

        response_uk = self.client.get(f"/uk/hub/{self.page.slug}/delete/")
        self.assertEqual(response_uk.status_code, 200)
