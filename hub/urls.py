from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("list/", views.ManagePageListView.as_view(), name="manage_page_list"),
    path("create/", views.PageCreateView.as_view(), name="page_create"),
    path("<slug:slug>/edit/", views.PageUpdateView.as_view(), name="page_edit"),
    path("<slug:slug>/delete/", views.PageDeleteView.as_view(), name="page_delete"),
    path(
        "<slug:slug>/section/",
        views.PageSectionUpdateView.as_view(),
        name="page_section_update",
    ),
    path(
        "section/<uuid:pk>/delete/",
        views.SectionDeleteView.as_view(),
        name="delete_section",
    ),
    path(
        "section/<uuid:section_id>/content/<model_name>/create/",
        views.ContentCreateUpdateView.as_view(),
        name="section_content_create",
    ),
    path(
        "section/<uuid:section_id>/content/<model_name>/<uuid:id>/",
        views.ContentCreateUpdateView.as_view(),
        name="section_content_update",
    ),
    path(
        "content/<uuid:id>/display/",
        views.ContentDisplayView.as_view(),
        name="section_content_display",
    ),
    path(
        "content/<uuid:id>/hide/",
        views.ContentHideView.as_view(),
        name="section_content_hide",
    ),
    path(
        "content/<uuid:id>/delete/",
        views.ContentDeleteView.as_view(),
        name="section_content_delete",
    ),
    path(
        "section/<uuid:section_id>/",
        views.SectionContentListView.as_view(),
        name="section_content_list",
    ),
    path(
        "section/<uuid:id>/publish/",
        views.SectionPublishView.as_view(),
        name="publish_section",
    ),
    path(
        "section/<uuid:id>/unpublish/",
        views.SectionUnpublishView.as_view(),
        name="unpublish_section",
    ),
    path("section/order/", views.SectionOrderView.as_view(), name="section_order"),
    path("content/order/", views.ContentOrderView.as_view(), name="content_order"),
    path("global-search/", views.global_search, name="global_search"),
]
