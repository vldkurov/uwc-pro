from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from hub.models import Section, Page, Content


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
