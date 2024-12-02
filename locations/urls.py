from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("", views.DivisionRedirectView.as_view(), name="division_redirect"),
    path("<slug:slug>/", views.DivisionListView.as_view(), name="division_list"),
    path("create", views.DivisionCreateView.as_view(), name="division_create"),
    path("<slug:slug>/edit/", views.DivisionUpdateView.as_view(), name="division_edit"),
    path(
        "<slug:slug>/delete", views.DivisionDeleteView.as_view(), name="division_delete"
    ),
    path("division/order/", views.DivisionOrderView.as_view(), name="division_order"),
    path(
        "<slug:division_slug>/branch/create/",
        views.BranchCreateUpdateView.as_view(),
        name="division_branch_create",
    ),
    path(
        "<slug:division_slug>/branch/<slug:branch_slug>/",
        views.BranchCreateUpdateView.as_view(),
        name="division_branch_update",
    ),
    path(
        "<slug:division_slug>/branch/<slug:branch_slug>/delete/",
        views.BranchDeleteView.as_view(),
        name="division_branch_delete",
    ),
    path(
        "<slug:division_slug>/branch/<slug:branch_slug>/display/",
        views.BranchDisplayView.as_view(),
        name="division_branch_display",
    ),
    path(
        "<slug:division_slug>/branch/<slug:branch_slug>/hide/",
        views.BranchHideView.as_view(),
        name="division_branch_hide",
    ),
]
