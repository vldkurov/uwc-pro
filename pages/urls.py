from django.urls import path, re_path

from . import views

urlpatterns = [
    # path("", views.HomePageView.as_view(), name="home"),
    path("", views.GenericPageView.as_view(), {"slug": "home"}, name="home"),
    re_path(
        r"^(?!public-search)(?P<slug>[\w-]+)/$",
        views.GenericPageView.as_view(),
        name="page",
    ),
    path(
        "locations/redirect",
        views.RedirectToFirstDivisionView.as_view(),
        name="locations_redirect",
    ),
    path("locations/<slug:slug>/", views.LocationsPageView.as_view(), name="locations"),
    path("public-search/", views.public_search, name="public_search"),
]
