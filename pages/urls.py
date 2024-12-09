from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("<slug:slug>/", views.GenericPageView.as_view(), name="page"),
    path(
        "locations/redirect",
        views.RedirectToFirstDivisionView.as_view(),
        name="locations_redirect",
    ),
    path("locations/<slug:slug>/", views.LocationsPageView.as_view(), name="locations"),
]
