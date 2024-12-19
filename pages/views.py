from django.contrib.postgres.search import (
    SearchVector,
    SearchRank,
    TrigramSimilarity,
    SearchQuery,
)
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import select_template, TemplateDoesNotExist
from django.views import View
from django.views.generic import TemplateView
from environs import Env

from hub.models import Section, Page, Content, Text, File, Image, Video, URL
from locations.models import Division, Branch, Person
from .forms import SearchForm

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
                "id": str(location.id),
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


def public_search(request):
    form = SearchForm()
    query = None
    results = []

    if "query" in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data["query"]
            search_query = SearchQuery(query)

            # pages = Page.objects.annotate(
            #     search=SearchVector("title_en", "title_uk")
            # ).filter(search=query)

            pages = (
                Page.objects.annotate(
                    search=SearchVector("title_en", "title_uk"),
                    rank=SearchRank(SearchVector("title_en", "title_uk"), search_query),
                    similarity=TrigramSimilarity("title_en", query)
                    + TrigramSimilarity("title_uk", query),
                )
                .filter(Q(search=query) | Q(similarity__gte=0.1))
                .order_by("-similarity", "-rank")
            )

            # sections = Section.published.annotate(
            #     search=SearchVector("title_en", "title_uk")
            # ).filter(search=query)

            sections = (
                Section.published.annotate(
                    search=SearchVector("title_en", "title_uk"),
                    rank=SearchRank(SearchVector("title_en", "title_uk"), search_query),
                    similarity=TrigramSimilarity("title_en", query)
                    + TrigramSimilarity("title_uk", query),
                )
                .filter(Q(search=query) | Q(similarity__gte=0.1))
                .order_by("-similarity", "-rank")
            )

            # text_content = (
            #     Text.objects.filter(
            #         id__in=Content.displayed.filter(
            #             content_type__model="text"
            #         ).values_list("object_id", flat=True)
            #     )
            #     .annotate(
            #         search=SearchVector("content_en", "content_uk"),
            #     )
            #     .filter(search=query)
            # )

            text_content = (
                Text.objects.filter(
                    id__in=Content.displayed.filter(
                        content_type__model="text"
                    ).values_list("object_id", flat=True)
                )
                .annotate(
                    search=SearchVector("content_en", "content_uk"),
                    rank=SearchRank(
                        SearchVector("content_en", "content_uk"), search_query
                    ),
                    similarity=TrigramSimilarity("content_en", query)
                    + TrigramSimilarity("content_uk", query),
                )
                .filter(Q(search=query) | Q(similarity__gte=0.01))
                .order_by("-similarity", "-rank")
            )

            file_content = (
                File.objects.filter(
                    id__in=Content.displayed.filter(
                        content_type__model="file"
                    ).values_list("object_id", flat=True)
                )
                .annotate(search=SearchVector("content"))
                .filter(search=query)
            )

            image_content = (
                Image.objects.filter(
                    id__in=Content.displayed.filter(
                        content_type__model="image"
                    ).values_list("object_id", flat=True)
                )
                .annotate(search=SearchVector("content"))
                .filter(search=query)
            )

            video_content = (
                Video.objects.filter(
                    id__in=Content.displayed.filter(
                        content_type__model="video"
                    ).values_list("object_id", flat=True)
                )
                .annotate(
                    search=SearchVector(
                        "content",
                    )
                )
                .filter(search=query)
            )

            url_content = (
                URL.objects.filter(
                    id__in=Content.displayed.filter(
                        content_type__model="url"
                    ).values_list("object_id", flat=True)
                )
                .annotate(search=SearchVector("content"))
                .filter(search=query)
            )

            # divisions = Division.objects.annotate(
            #     search=SearchVector("title_en", "title_uk")
            # ).filter(search=query)

            divisions = (
                Division.objects.annotate(
                    search=SearchVector("title_en", "title_uk"),
                    rank=SearchRank(SearchVector("title_en", "title_uk"), search_query),
                    similarity=TrigramSimilarity("title_en", query)
                    + TrigramSimilarity("title_uk", query),
                )
                .filter(Q(search=query) | Q(similarity__gte=0.01))
                .order_by("-similarity", "-rank")
            )

            # branches = Branch.displayed.annotate(
            #     search=SearchVector("title_en", "title_uk", "address_en", "address_uk")
            # ).filter(search=query)

            branches = (
                Branch.displayed.annotate(
                    search=SearchVector(
                        "title_en", "title_uk", "address_en", "address_uk"
                    ),
                    rank=SearchRank(
                        SearchVector(
                            "title_en", "title_uk", "address_en", "address_uk"
                        ),
                        search_query,
                    ),
                    similarity=TrigramSimilarity("title_en", query)
                    + TrigramSimilarity("title_uk", query)
                    + TrigramSimilarity("address_en", query)
                    + TrigramSimilarity("address_uk", query),
                )
                .filter(Q(search=query) | Q(similarity__gte=0.5))
                .order_by("-similarity", "-rank")
            )

            persons = (
                Person.objects.annotate(
                    search=SearchVector(
                        "first_name_en", "last_name_en", "first_name_uk", "last_name_uk"
                    )
                )
                .filter(search=query)
                .filter(
                    Q(branch_chair__status=Branch.Status.DISPLAY)
                    | Q(parish_priest__status=Branch.Status.DISPLAY)
                    | Q(branch_secretary__status=Branch.Status.DISPLAY)
                )
                .distinct()
            )

            results = (
                list(pages)
                + list(sections)
                + list(text_content)
                + list(file_content)
                + list(image_content)
                + list(video_content)
                + list(url_content)
                + list(divisions)
                + list(branches)
                + list(persons)
            )

    return render(
        request,
        "pages/public_search.html",
        {
            "form": form,
            "query": query,
            "results": results,
        },
    )
