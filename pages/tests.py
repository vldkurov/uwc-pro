from django.test import TestCase
from django.urls import reverse, resolve

from hub.models import Page
from .views import AboutPageView, HomePageView


class HomePageTests(TestCase):
    def setUp(self):
        url = reverse("home")
        self.response = self.client.get(url)

    def test_url_exists_at_desired_location(self):
        self.assertEqual(self.response.status_code, 200)

    def test_homepage_template(self):
        self.assertTemplateUsed(self.response, "pages/home.html")

    def test_homepage_contains_correct_html(self):
        self.assertContains(self.response, "Home")

    def test_homepage_does_not_contain_incorrect_html(self):
        self.assertNotContains(self.response, "Hi there! I should not be on the page.")

    def test_homepage_url_resolves_homepageview(self):
        view = resolve("/en/")
        self.assertEqual(view.func.__name__, HomePageView.as_view().__name__)


class AboutPageTests(TestCase):
    def setUp(self):
        self.page = Page.objects.create(
            title="About Us",
            slug="about-us",
        )
        self.url = reverse("about", kwargs={"slug": "about-us"})

    def test_aboutpage_status_code(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_aboutpage_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "pages/about-us.html")

    def test_aboutpage_contains_correct_html(self):
        response = self.client.get(self.url)
        self.assertContains(response, "About Us")

    def test_aboutpage_does_not_contain_incorrect_html(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "Hi there! I should not be on the page.")

    def test_aboutpage_url_resolves_aboutpageview(self):
        view = resolve("/en/about/")
        self.assertEqual(view.func.__name__, AboutPageView.as_view().__name__)
