from django.test import TestCase
from django.urls import reverse, resolve

from hub.models import Page
from locations.models import Division, Branch
from .views import GenericPageView, HomePageView


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


class GenericPageTests(TestCase):
    def setUp(self):
        self.page = Page.objects.create(
            title="About Us",
            slug="about-us",
        )
        self.url = reverse("page", kwargs={"slug": "about-us"})

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
        view = resolve("/en/about-us/")
        self.assertEqual(view.func.__name__, GenericPageView.as_view().__name__)


class RedirectToFirstDivisionViewTests(TestCase):
    def setUp(self):
        # Create some sample divisions
        self.div1 = Division.objects.create(
            title="Division 1", slug="division-1", order=1
        )
        self.div2 = Division.objects.create(
            title="Division 2", slug="division-2", order=2
        )

    def test_redirect_to_first_division(self):
        """Test redirection to the first division based on order."""
        response = self.client.get(reverse("locations_redirect"))
        self.assertRedirects(
            response, reverse("locations", kwargs={"slug": self.div1.slug})
        )

    def test_redirect_to_home_if_no_divisions(self):
        """Test redirection to home page if no divisions exist."""
        # Clear all divisions
        Division.objects.all().delete()
        response = self.client.get(reverse("locations_redirect"))
        self.assertRedirects(response, reverse("home"))

    def test_redirect_with_multiple_divisions(self):
        """Test redirection when multiple divisions exist."""
        # Add a new division with lower order
        Division.objects.create(title="Division 0", slug="division-0", order=0)

        response = self.client.get(reverse("locations_redirect"))
        self.assertRedirects(
            response, reverse("locations", kwargs={"slug": "division-0"})
        )


class LocationsPageViewTests(TestCase):
    def setUp(self):
        # Create sample divisions
        self.division1 = Division.objects.create(
            title="Division 1", slug="division-1", order=1
        )
        self.division2 = Division.objects.create(
            title="Division 2", slug="division-2", order=2
        )

        # Create sample branch linked to division 1
        self.branch1 = Branch.objects.create(
            division=self.division1,
            title="Branch 1",
            address_en="Address 1",
            lat=51.5074,
            lng=-0.1278,
            status=Branch.Status.DISPLAY,
        )

        # Create sample branch linked to division 2
        self.branch2 = Branch.objects.create(
            division=self.division2,
            title="Branch 2",
            address_en="Address 2",
            lat=52.5074,
            lng=-1.1278,
            status=Branch.Status.DISPLAY,
        )

    def test_template_rendering(self):
        """Test that the location template renders correctly."""
        response = self.client.get(
            reverse("locations", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/locations.html")

    def test_context_with_valid_slug(self):
        """Test context data with a valid division slug."""
        response = self.client.get(
            reverse("locations", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Check if context has divisions
        self.assertIn("divisions", response.context)
        self.assertIn("current_division", response.context)
        self.assertIn("locations", response.context)

        # Verify the current division is correct
        self.assertEqual(response.context["current_division"], self.division1)

        # Verify locations are correct
        locations = response.context["locations"]
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]["title"], self.branch1.title)

    def test_context_with_invalid_slug(self):
        """Test a 404 error for an invalid division slug."""
        response = self.client.get(
            reverse("locations", kwargs={"slug": "invalid-slug"})
        )
        self.assertEqual(response.status_code, 404)

    def test_multiple_divisions_in_context(self):
        """Test that all divisions are present in context."""
        response = self.client.get(
            reverse("locations", kwargs={"slug": self.division2.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Check all divisions are present
        divisions = response.context["divisions"]
        self.assertEqual(len(divisions), 2)
        self.assertIn(self.division1, divisions)
        self.assertIn(self.division2, divisions)

    def test_branch_details_in_context(self):
        """Test that branch details are included in context."""
        response = self.client.get(
            reverse("locations", kwargs={"slug": self.division1.slug})
        )
        self.assertEqual(response.status_code, 200)

        # Retrieve updated branch from the database
        branch = Branch.objects.get(id=self.branch1.id)

        # Check that only 1 location is in the context
        locations = response.context["locations"]
        self.assertEqual(len(locations), 1)

        # Validate the branch details
        location = locations[0]
        self.assertEqual(location["title"], self.branch1.title)
        self.assertAlmostEqual(
            location["lat"], branch.lat, places=4
        )  # Compare dynamically
        self.assertAlmostEqual(
            location["lng"], branch.lng, places=4
        )  # Compare dynamically

    def test_branch_hidden_status_exclusion(self):
        """Test that branches with HIDDEN status are excluded."""
        # Create a branch with 'HIDE' status
        self.hidden_branch = Branch.objects.create(
            division=self.division1,
            title="Hidden Branch",
            address_en="Address 2",
            lat=51.5074,
            lng=-0.1278,
            status=Branch.Status.HIDE,
        )

        # Make a request to the location page
        response = self.client.get(
            reverse("locations", kwargs={"slug": self.division1.slug})
        )

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Get locations context
        locations = response.context["locations"]

        # Ensure the hidden branch is not included
        for location in locations:
            self.assertNotEqual(location["title"], self.hidden_branch.title)
