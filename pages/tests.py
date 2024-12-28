from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse, resolve

from hub.models import Page, Section, Text, Content, File, Video, URL
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


class PublicSearchTests(TestCase):
    def setUp(self):
        self.page = Page.objects.create(
            title_en="Example Page", title_uk="Приклад Сторінка"
        )
        self.section = Section.objects.create(
            page=self.page,
            title_en="Example Section",
            title_uk="Приклад Розділ",
            status=Section.Status.PUBLISHED,
        )
        self.text = Text.objects.create(
            content_en="Example content",
            content_uk="Приклад вміст",
        )
        content = Content.objects.create(
            section=self.section,
            object_id=self.text.id,
            content_type=ContentType.objects.get_for_model(Text),
            status=Content.Status.DISPLAY,
        )
        self.division = Division.objects.create(title_en="Example Division")
        self.branch = Branch.objects.create(
            division=self.division,
            title_en="Example Branch",
            address_en="123 Example St",
            status=Branch.Status.DISPLAY,
        )

    def test_load_page_without_query(self):
        """Test that the page loads without query parameters."""
        response = self.client.get(reverse("public_search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found.")

    def test_search_with_valid_query(self):
        """Test that valid queries return expected results."""
        response = self.client.get(reverse("public_search"), {"query": "Example"})
        self.assertEqual(response.status_code, 200)

        results = response.context["results"]

        self.assertIn(self.page, results)
        self.assertIn(self.section, results)
        self.assertIn(self.text, results)
        self.assertIn(self.division, results)
        self.assertIn(self.branch, results)

    def test_partial_match_query(self):
        """Test that partial matches return results."""
        response = self.client.get(reverse("public_search"), {"query": "Exampl"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertIn(self.page, results)

    def test_branch_hidden_exclusion(self):
        """Test that hidden branches are excluded from results."""
        hidden_branch = Branch.objects.create(
            division=self.division,
            title_en="Hidden Branch",
            address_en="123 Example St",
            status=Branch.Status.HIDE,
        )
        response = self.client.get(reverse("public_search"), {"query": "Hidden"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertNotIn(hidden_branch, results)

    def test_search_ranking(self):
        """Test ranking of results by relevance."""
        less_relevant_page = Page.objects.create(title_en="Less Relevant Example")
        response = self.client.get(reverse("public_search"), {"query": "Example"})
        results = response.context["results"]
        self.assertGreater(results.index(less_relevant_page), results.index(self.page))

    def test_trigram_similarity(self):
        """Test trigram similarity with typos."""
        response = self.client.get(reverse("public_search"), {"query": "Exampl"})
        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertIn(self.page, results)

    def test_exclude_inactive_content(self):
        """Test that inactive content is excluded from results."""
        inactive_text = Text.objects.create(
            content_en="Hidden text", content_uk="Прихований текст"
        )
        inactive_file = File.objects.create(title="Hidden File")
        inactive_video = Video.objects.create(title="Hidden Video")
        inactive_url = URL.objects.create(title="Hidden URL")

        Content.objects.create(
            section=self.section,
            object_id=inactive_text.id,
            content_type=ContentType.objects.get_for_model(Text),
            status=Content.Status.HIDE,
        )
        Content.objects.create(
            section=self.section,
            object_id=inactive_file.id,
            content_type=ContentType.objects.get_for_model(File),
            status=Content.Status.HIDE,
        )
        Content.objects.create(
            section=self.section,
            object_id=inactive_video.id,
            content_type=ContentType.objects.get_for_model(Video),
            status=Content.Status.HIDE,
        )
        Content.objects.create(
            section=self.section,
            object_id=inactive_url.id,
            content_type=ContentType.objects.get_for_model(URL),
            status=Content.Status.HIDE,
        )

        response = self.client.get(reverse("public_search"), {"query": "Hidden"})
        self.assertEqual(response.status_code, 200)

        results = response.context["results"]
        self.assertNotIn(inactive_text, results)
        self.assertNotIn(inactive_file, results)
        self.assertNotIn(inactive_video, results)
        self.assertNotIn(inactive_url, results)

    def test_large_volume_of_results(self):
        """Test that search handles large volumes of results."""
        pages = [
            Page(
                title_en=f"Example Page {i}",
                slug=f"example-page-{i}",
            )
            for i in range(1000)
        ]

        Page.objects.bulk_create(pages)

        response = self.client.get(reverse("public_search"), {"query": "Example"})
        self.assertEqual(response.status_code, 200)

        results = response.context["results"]
        self.assertGreaterEqual(len(results), 1000)
