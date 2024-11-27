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
    path("<slug:slug>/", views.BranchDetailView.as_view(), name="branch_detail"),
    path("division/order/", views.DivisionOrderView.as_view(), name="division_order"),
]
