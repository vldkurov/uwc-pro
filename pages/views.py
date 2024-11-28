from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from django.views import View

from hub.models import Section, Page, Content
from locations.models import Division


class HomePageView(TemplateView):
    template_name = "pages/home.html"


class AboutPageView(TemplateView):
    template_name = "pages/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slug = kwargs.get("slug")

        page = get_object_or_404(Page, slug=slug)
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
        return context
