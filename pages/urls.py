from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("about/<slug:slug>/", views.AboutPageView.as_view(), name="about"),
    path(
        "locations/",
        views.RedirectToFirstDivisionView.as_view(),
        name="locations_redirect",
    ),
    path("locations/<slug:slug>/", views.LocationsPageView.as_view(), name="locations"),
]
