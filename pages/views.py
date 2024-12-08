from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import select_template, TemplateDoesNotExist
from django.views import View
from django.views.generic import TemplateView
from environs import Env

from hub.models import Section, Page, Content
from locations.models import Division, Branch

env = Env()
env.read_env()


class HomePageView(TemplateView):
    template_name = "pages/home.html"


class GenericPageView(TemplateView):

    def get_template_names(self):
        slug = self.kwargs.get("slug")
        specific_template = f"pages/{slug}.html"
        default_template = "pages/page.html"

        try:
            select_template([specific_template])
            return [specific_template]
        except TemplateDoesNotExist:
            return [default_template]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slug = kwargs.get("slug")

        try:
            page = Page.objects.get(slug=slug)
        except Page.DoesNotExist:
            raise Http404("The requested page does not exist.")

        context["page"] = page

        sections = page.sections.filter(
            status=Section.Status.PUBLISHED
        ).prefetch_related("contents__item")
        context["sections"] = [
            {
                "section": section,
                "contents": [
                    {
                        "type": content.item.__class__.__name__.lower(),
                        "content": content.item,
                    }
                    for content in section.contents.filter(
                        status=Content.Status.DISPLAY
                    )
                ],
            }
            for section in sections
        ]

        return context


class RedirectToFirstDivisionView(View):
    def get(self, request, *args, **kwargs):
        first_division = Division.objects.order_by("order").first()
        if first_division:
            return redirect("locations", slug=first_division.slug)
        return redirect("home")


class LocationsPageView(TemplateView):
    template_name = "pages/locations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        divisions = Division.objects.all()
        slug = self.kwargs.get("slug")

        current_division = (
            get_object_or_404(Division, slug=slug) if slug else divisions.first()
        )

        context["divisions"] = divisions
        context["current_division"] = current_division

        googlemaps_api_key = env.str("GOOGLE_MAPS_API_KEY")
        locations = Branch.objects.filter(
            division=current_division,
            status=Branch.Status.DISPLAY,
        )

        locations = [
            {
                "title": location.title,
                "parish_priest": (
                    str(location.parish_priest) if location.parish_priest else ""
                ),
                "branch_chair": (
                    str(location.branch_chair) if location.branch_chair else ""
                ),
                "branch_secretary": (
                    str(location.branch_secretary) if location.branch_secretary else ""
                ),
                "formatted_address": location.formatted_address or "",
                "other_details": location.other_details or "",
                "url": location.url or "",
                "phones": [phone.number for phone in location.phones.all()],
                "emails": [email.email for email in location.emails.all()],
                "lat": location.lat,
                "lng": location.lng,
            }
            for location in locations
        ]

        context["googlemaps_api_key"] = googlemaps_api_key
        context["locations"] = locations

        return context
