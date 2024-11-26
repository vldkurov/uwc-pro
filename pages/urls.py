from django.urls import path

from .views import HomePageView, AboutPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("<slug:slug>/", AboutPageView.as_view(), name="about"),
]
