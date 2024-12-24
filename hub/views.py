import logging
import os
import uuid

from braces.views import CsrfExemptMixin, JsonRequestResponseMixin
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.postgres.search import SearchVector, SearchRank
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models.fields.files import FieldFile
from django.forms.models import model_to_dict
from django.forms.models import modelform_factory
from django.http import HttpResponseForbidden, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser
from locations.models import Division, Branch, Person
from payments.models import Donor, Donation
from .forms import SectionFormSet, SectionForm, PageForm, SearchForm
from .models import Page, Section, Content, Text, File, Image, Video, URL

logger = logging.getLogger(__name__)


def custom_permission_denied_view(request, exception=None):
    return render(request, "hub/403.html", status=403)


class DashboardView(TemplateView):
    template_name = "hub/dashboard.html"


class ModifiedByMixin:
    def get_queryset(self):
        return super().get_queryset().all()


class ModifiedByEditMixin:
    def __init__(self):
        self.request = None

    def form_valid(self, form):
        form.instance.modified_by = self.request.user
        return super().form_valid(form)


class ModifiedByPageMixin(ModifiedByMixin, LoginRequiredMixin, PermissionRequiredMixin):
    model = Page
    success_url = reverse_lazy("manage_page_list")


class ModifiedByPageEditMixin(ModifiedByPageMixin, ModifiedByEditMixin):
    template_name = "hub/manage/page/form.html"


class ManagePageListView(ModifiedByPageMixin, ListView):
    model = Page
    template_name = "hub/manage/page/list.html"
    context_object_name = "page_list"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.view_page"


class PageCreateView(ModifiedByPageEditMixin, CreateView):
    form_class = PageForm
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.add_page"


class PageUpdateView(ModifiedByPageEditMixin, UpdateView):
    model = Page
    form_class = PageForm
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.change_page"


class PageDeleteView(ModifiedByPageMixin, DeleteView):
    template_name = "hub/manage/page/delete.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.delete_page"


class SectionCreateView(ModifiedByPageEditMixin, CreateView):
    model = Section
    form_class = SectionForm
    template_name = "hub/manage/section/formset.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.add_section"

    def form_valid(self, form):
        form.instance.page = get_object_or_404(Page, slug=self.kwargs["slug"])
        form.instance.modified_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("page_section_update", kwargs={"slug": self.kwargs["slug"]})


class PageSectionUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, TemplateResponseMixin, View
):
    template_name = "hub/manage/section/formset.html"
    page = None
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.view_section"

    def get_formset(self, data=None):
        return SectionFormSet(
            instance=self.page,
            data=data,
        )

    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        self.page = get_object_or_404(Page, slug=slug)
        return super().dispatch(request, slug)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response({"page": self.page, "formset": formset})

    def post(self, request, *args, **kwargs):

        if "add_new_section" in request.POST:
            if not request.user.has_perm("hub.add_section"):
                raise PermissionDenied
            Section.objects.create(page=self.page)

        formset = self.get_formset(data=request.POST)

        for form in formset:
            form.has_changed = lambda: True

        for form in formset.forms:
            section = form.instance
            section_prefix = form.prefix

            if (
                f"{section_prefix}-request_update_en" in request.POST
                and not section.original_data
            ):
                self.create_section_copy(section)
            if (
                f"{section_prefix}-request_update_uk" in request.POST
                and not section.original_data
            ):
                self.create_section_copy(section)

        if formset.is_valid():
            sections = formset.save(commit=False)

            for form, section in zip(formset.forms, sections):
                section_prefix = form.prefix

                if f"{section_prefix}-request_update_en" in request.POST:
                    if not request.user.has_perm("hub.request_update_en"):
                        raise PermissionDenied
                    section.is_update_pending_en = True

                if f"{section_prefix}-request_update_uk" in request.POST:
                    if not request.user.has_perm("hub.request_update_uk"):
                        raise PermissionDenied
                    section.is_update_pending_uk = True

                if f"{section_prefix}-confirm_update_en" in request.POST:
                    if not request.user.has_perm("hub.confirm_update_en"):
                        raise PermissionDenied
                    section.is_update_pending_en = False
                    section.is_update_confirmed_en = True
                    self.update_section_copy(section, "title_draft_en")

                if f"{section_prefix}-confirm_update_uk" in request.POST:
                    if not request.user.has_perm("hub.confirm_update_uk"):
                        raise PermissionDenied
                    section.is_update_pending_uk = False
                    section.is_update_confirmed_uk = True
                    self.update_section_copy(section, "title_draft_uk")

                if f"{section_prefix}-reject_update_en" in request.POST:
                    if not request.user.has_perm("hub.reject_update_en"):
                        raise PermissionDenied
                    section.is_update_pending_en = False
                    section.is_update_confirmed_en = False
                    self.restore_section_from_copy(section)

                if f"{section_prefix}-reject_update_uk" in request.POST:
                    if not request.user.has_perm("hub.reject_update_en"):
                        raise PermissionDenied
                    section.is_update_pending_uk = False
                    section.is_update_confirmed_uk = False
                    self.restore_section_from_copy(section)

                section.modified_by = request.user
                section.save()

            return redirect("page_section_update", slug=self.page.slug)

        return self.render_to_response({"page": self.page, "formset": formset})

    @staticmethod
    def create_section_copy(section):
        fields_to_include = ["title_draft_en", "title_draft_uk"]
        section_copy_data = model_to_dict(section, fields=fields_to_include)
        section.original_data = section_copy_data
        section.save()

    @staticmethod
    def update_section_copy(section, field_to_update):
        if section.original_data:
            section.original_data[field_to_update] = getattr(section, field_to_update)
            section.save(update_fields=["original_data"])

    @staticmethod
    def restore_section_from_copy(section):
        if section.original_data:
            for field, value in section.original_data.items():
                setattr(section, field, value)
            section.save()


class SectionDeleteView(ModifiedByPageMixin, DeleteView):
    model = Section
    template_name = "hub/manage/section/delete.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.delete_section"

    def dispatch(self, request, *args, **kwargs):
        self.section = self.get_object()
        if self.section.status != Section.Status.DRAFT:
            return HttpResponseForbidden("Cannot delete a published section.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            "page_section_update", kwargs={"slug": self.section.page.slug}
        )


class SectionPublishView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "hub/manage/section/publish.html"
    model = Section
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.publish_section"

    def get(self, request, *args, **kwargs):
        section = get_object_or_404(Section, id=kwargs.get("id"))
        return render(request, self.template_name, {"section": section})

    @staticmethod
    def post(request, *args, **kwargs):
        section = get_object_or_404(Section, id=kwargs.get("id"))

        if section.status == Section.Status.PUBLISHED:
            messages.error(request, "This section is already published.")
            return redirect("page_section_update", slug=section.page.slug)

        if not (section.is_update_confirmed_en and section.is_update_confirmed_uk):
            messages.error(
                request, "Please confirm all content updates before publishing."
            )
            return redirect("page_section_update", slug=section.page.slug)

        section.title_en = section.title_draft_en
        section.title_uk = section.title_draft_uk
        section.status = Section.Status.PUBLISHED
        section.original_data = None
        section.is_update_pending_en = False
        section.is_update_confirmed_en = False
        section.is_update_pending_uk = False
        section.is_update_confirmed_uk = False
        section.save()

        messages.success(request, "Section published successfully.")
        return redirect("page_section_update", slug=section.page.slug)


class SectionUnpublishView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "hub/manage/section/unpublish.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.unpublish_section"

    def get(self, request, *args, **kwargs):
        section = get_object_or_404(Section, id=kwargs.get("id"))
        if section.status != Section.Status.PUBLISHED:
            return HttpResponseForbidden("Only published sections can be unpublished.")
        return render(request, self.template_name, {"section": section})

    @staticmethod
    def post(request, *args, **kwargs):
        section = get_object_or_404(Section, id=kwargs.get("id"))
        if section.status != Section.Status.PUBLISHED:
            return HttpResponseForbidden("Only published sections can be unpublished.")
        section.status = Section.Status.DRAFT
        section.save()
        return redirect("page_section_update", slug=section.page.slug)


class ContentCreateUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, TemplateResponseMixin, View
):
    section = None
    model = None
    obj = None
    template_name = "hub/manage/content/form.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.view_content"

    def get_model(self, model_name):
        if model_name in ["text", "file", "image", "video", "url"]:
            return apps.get_model(app_label="hub", model_name=model_name)
        return None

    @staticmethod
    def get_form(model, *args, **kwargs):
        if hasattr(model, "content_draft_en") and hasattr(model, "content_draft_uk"):
            fields_to_include = ("content_draft_en", "content_draft_uk")
        else:
            fields_to_include = ("content_draft",)
        form = modelform_factory(model, fields=fields_to_include)
        return form(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        section_id = kwargs.get("section_id")
        model_name = kwargs.get("model_name")
        object_id = kwargs.get("id", None)

        if not object_id and not request.user.has_perm("hub.add_content"):
            raise PermissionDenied

        self.section = get_object_or_404(Section, id=section_id)
        self.model = self.get_model(model_name)

        if not self.model:
            raise Http404(_("Invalid model name."))

        if object_id:
            self.obj = get_object_or_404(self.model, id=object_id)

        return super().dispatch(request, section_id, model_name, object_id)

    def get(self, request, *args, **kwargs):
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({"form": form, "object": self.obj})

    def post(self, request, *args, **kwargs):
        form = self.get_form(
            self.model, instance=self.obj, data=request.POST, files=request.FILES
        )

        if any("request_update" in key for key in request.POST):

            if not request.user.has_perm("hub.request_update"):
                raise PermissionDenied

            if not self.obj:
                obj = form.save(commit=False)

                original_content_draft_en = getattr(obj, "content_draft_en", None)
                original_content_draft_uk = getattr(obj, "content_draft_uk", None)
                original_content_draft = getattr(obj, "content_draft", None)

                if isinstance(obj, Text):
                    obj.content_draft_en = None
                    obj.content_draft_uk = None
                else:
                    obj.content_draft = None

                self.create_content_copy(obj)

                if isinstance(obj, Text):
                    obj.content_draft_en = original_content_draft_en
                    obj.content_draft_uk = original_content_draft_uk
                else:
                    obj.content_draft = original_content_draft

                obj.title = f"Content {self.section.order + 1}.{self.section.contents.count() + 1}"
                obj.modified_by = request.user
                obj.save()

                Content.objects.create(section=self.section, item=obj)
                self.obj = obj

            else:
                obj = self.obj or form.instance
                if not obj.original_data:
                    self.create_content_copy(obj)

            if isinstance(obj, Text):
                if "request_update_en" in request.POST:
                    if not request.user.has_perm("hub.request_update_en"):
                        raise PermissionDenied
                    obj.is_update_pending_en = True
                if "request_update_uk" in request.POST:
                    if not request.user.has_perm("hub.request_update_uk"):
                        raise PermissionDenied
                    obj.is_update_pending_uk = True
            else:
                if not request.user.has_perm("hub.request_update"):
                    raise PermissionDenied
                obj.is_update_pending = True

            if form.is_valid():
                obj = form.save(commit=False)
                obj.modified_by = request.user
                obj.save()

            return redirect(
                "section_content_update",
                section_id=self.section.id,
                model_name=self.model.__name__.lower(),
                id=self.obj.id,
            )

        if any("confirm_update" in key for key in request.POST):

            if not request.user.has_perm("hub.confirm_update"):
                raise PermissionDenied

            obj = form.save(commit=False)

            if isinstance(obj, Text):
                if "confirm_update_en" in request.POST:
                    if not request.user.has_perm("hub.confirm_update_en"):
                        raise PermissionDenied
                    obj.is_update_pending_en = False
                    obj.is_update_confirmed_en = True
                    self.update_content_copy(obj, "content_draft_en")
                if "confirm_update_uk" in request.POST:
                    if not request.user.has_perm("hub.confirm_update_uk"):
                        raise PermissionDenied
                    obj.is_update_pending_uk = False
                    obj.is_update_confirmed_uk = True
                    self.update_content_copy(obj, "content_draft_uk")
            else:
                if not request.user.has_perm("hub.confirm_update"):
                    raise PermissionDenied
                if obj.original_data and "content_draft" in obj.original_data:
                    previous_file = obj.original_data.get("content_draft")
                    if previous_file:
                        try:
                            obj.content.storage.delete(previous_file)
                            print(
                                f"Previous file '{previous_file}' successfully deleted."
                            )
                        except Exception as e:
                            print(f"Error deleting file '{previous_file}': {e}")

                obj.is_update_pending = False
                obj.is_update_confirmed = True

                self.update_content_copy(obj, "content_draft")

            obj.modified_by = request.user
            obj.save()

            return redirect(
                "section_content_update",
                section_id=self.section.id,
                model_name=self.model.__name__.lower(),
                id=self.obj.id,
            )

        if any("reject_update" in key for key in request.POST):
            if not request.user.has_perm("hub.reject_update"):
                raise PermissionDenied

            obj = form.save(commit=False)

            if obj.original_data and all(
                value is None for value in obj.original_data.values()
            ):
                if hasattr(obj, "content") and isinstance(obj.content, FieldFile):
                    obj.content.delete(save=False)

                if hasattr(obj, "content_draft") and isinstance(
                    obj.content_draft, FieldFile
                ):
                    obj.content_draft.delete(save=False)

                obj.delete()
                return redirect(
                    "section_content_list",
                    section_id=self.section.id,
                )

            if isinstance(obj, Text):
                if "reject_update_en" in request.POST:
                    if not request.user.has_perm("hub.reject_update_en"):
                        raise PermissionDenied
                    obj.is_update_pending_en = False
                    obj.is_update_confirmed_en = False
                    self.restore_content_from_copy(obj)
                if "reject_update_uk" in request.POST:
                    if not request.user.has_perm("hub.reject_update_uk"):
                        raise PermissionDenied
                    obj.is_update_pending_uk = False
                    obj.is_update_confirmed_uk = False
                    self.restore_content_from_copy(obj)
            else:
                if not request.user.has_perm("hub.reject_update"):
                    raise PermissionDenied

                if hasattr(obj, "content_draft") and obj.content_draft:
                    temp = os.path.basename(obj.content_draft.name)
                    try:
                        obj.content_draft.delete(save=False)
                        print(f"Draft file '{temp}' successfully deleted.")
                    except Exception as e:
                        print(f"Error deleting draft file '{temp}': {e}")

                obj.is_update_pending = False
                obj.is_update_confirmed = False

                self.restore_content_from_copy(obj)

            obj.modified_by = request.user
            obj.save()

            return redirect(
                "section_content_update",
                section_id=self.section.id,
                model_name=self.model.__name__.lower(),
                id=self.obj.id,
            )

        return self.render_to_response({"form": form, "object": self.obj})

    @staticmethod
    def create_content_copy(content):
        fields_to_include = [
            field.name
            for field in content._meta.fields
            if field.name.startswith("content_draft")
        ]

        content_copy_data = {}

        for field in fields_to_include:
            value = getattr(content, field, None)

            if isinstance(value, models.fields.files.FieldFile):
                content_copy_data[field] = value.name if value else None
            elif isinstance(value, str):
                content_copy_data[field] = value
            else:
                content_copy_data[field] = None

        content.original_data = content_copy_data
        content.save()

    @staticmethod
    def update_content_copy(content, field_to_update):
        if content.original_data:
            value = getattr(content, field_to_update, None)

            if isinstance(value, models.fields.files.FieldFile):
                content.original_data[field_to_update] = value.name if value else None
            elif isinstance(value, str):
                content.original_data[field_to_update] = value
            else:
                content.original_data[field_to_update] = None

            content.save(update_fields=["original_data"])

    @staticmethod
    def restore_content_from_copy(content):
        if content.original_data:
            for field, value in content.original_data.items():
                if hasattr(content, field):
                    model_field = content._meta.get_field(field)
                    if isinstance(model_field, models.FileField):
                        if value:
                            try:
                                content_field = getattr(content, field)
                                content_field.storage.open(value)
                                setattr(content, field, value)
                            except Exception as e:
                                setattr(content, field, None)
                                print(_(f"File '{value}' not found in storage: {e}"))
                        else:
                            setattr(content, field, None)
                    elif isinstance(model_field, models.URLField):
                        setattr(content, field, value)
                    else:
                        setattr(content, field, value)
            content.save()


class ContentDisplayView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "hub/manage/content/display.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.display"

    def get(self, request, *args, **kwargs):
        content = get_object_or_404(Content, id=kwargs.get("id"))
        return render(request, self.template_name, {"content": content})

    @staticmethod
    def post(request, *args, **kwargs):
        content = get_object_or_404(Content, id=kwargs.get("id"))

        item = content.item

        if isinstance(item, Text):

            if not (item.is_update_confirmed_en and item.is_update_confirmed_uk):
                messages.error(
                    request,
                    "Please confirm all content updates (EN and UK) before displaying.",
                )
                return redirect("section_content_list", section_id=content.section.id)

            item.content_en = item.content_draft_en
            item.content_uk = item.content_draft_uk
            item.is_update_pending_en = False
            item.is_update_confirmed_en = False
            item.is_update_pending_uk = False
            item.is_update_confirmed_uk = False
        else:
            if not item.is_update_confirmed:
                messages.error(
                    request, "Please confirm all content updates before displaying."
                )
                return redirect("section_content_list", section_id=content.section.id)

            item.content = item.content_draft
            item.is_update_pending = False
            item.is_update_confirmed = False

        item.original_data = None
        item.save()

        content.display()

        messages.success(request, "Content displayed successfully.")
        return redirect("section_content_list", section_id=content.section.id)


class ContentHideView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "hub/manage/content/hide.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.hide"

    def get(self, request, *args, **kwargs):
        content = get_object_or_404(Content, id=kwargs.get("id"))
        return render(request, self.template_name, {"content": content})

    @staticmethod
    def post(request, *args, **kwargs):
        content = get_object_or_404(Content, id=kwargs.get("id"))
        item = content.item

        if isinstance(item, Text):
            item.is_update_pending_en = False
            item.is_update_confirmed_en = False
            item.is_update_pending_uk = False
            item.is_update_confirmed_uk = False
        else:
            item.is_update_pending = False
            item.is_update_confirmed = False

        item.original_data = None
        item.save()

        content.hide()

        messages.success(request, "Content hidden successfully.")
        return redirect("section_content_list", section_id=content.section.id)


class ContentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "hub/manage/content/delete.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.delete_content"

    def get(self, request, *args, **kwargs):
        content = get_object_or_404(Content, id=kwargs.get("id"))
        return render(request, self.template_name, {"content": content})

    @staticmethod
    def post(request, *args, **kwargs):
        object_id = kwargs.get("id")
        content = get_object_or_404(Content, id=object_id)
        section = content.section

        if hasattr(content.item, "content") and isinstance(
            content.item.content, models.fields.files.FieldFile
        ):
            if content.item.content:
                content.item.content.delete(save=False)

        if hasattr(content.item, "content_draft") and isinstance(
            content.item.content_draft, models.fields.files.FieldFile
        ):
            if content.item.content_draft:
                content.item.content_draft.delete(save=False)

        content.item.delete()
        content.delete()

        return redirect("section_content_list", section.id)


class SectionContentListView(
    LoginRequiredMixin, PermissionRequiredMixin, TemplateResponseMixin, View
):
    template_name = "hub/manage/section/content_list.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "hub.view_content"

    def get(self, request, *args, **kwargs):
        section_id = kwargs.get("section_id")
        section = get_object_or_404(Section, id=section_id)
        return self.render_to_response(
            {
                "section": section,
            }
        )


class SectionOrderView(
    CsrfExemptMixin,
    JsonRequestResponseMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "hub.change_section_order"
    login_url = "account_login"
    redirect_field_name = "next"

    def handle_no_permission(self):
        return JsonResponse(
            {
                "error": str(
                    _("You do not have permission to change the section order.")
                )
            },
            status=403,
        )

    # def post(self, request):
    #     if not self.request_json:
    #         return JsonResponse(
    #             {"error": _("Request data is empty or invalid.")}, status=400
    #         )
    #
    #     for section_id, order in self.request_json.items():
    #         try:
    #             uuid.UUID(section_id)
    #         except ValueError:
    #             return JsonResponse(
    #                 {"error": _("Invalid section ID provided.")}, status=400
    #             )
    #
    #         Section.objects.filter(id=section_id).update(order=order)
    #
    #     return self.render_json_response({"saved": "OK"})

    def post(self, request):
        if not self.request_json:
            return JsonResponse(
                {"error": _("Request data is empty or invalid.")}, status=400
            )

        updated_sections = []
        for section_id, order in self.request_json.items():
            try:
                uuid.UUID(section_id)
            except ValueError:
                return JsonResponse(
                    {"error": _("Invalid section ID provided.")}, status=400
                )

            updated_count = Section.objects.filter(id=section_id).update(order=order)

            if updated_count == 0:
                return JsonResponse({"error": _("Section ID not found.")}, status=404)
            updated_sections.append(section_id)

        return self.render_json_response({"updated": updated_sections})


class ContentOrderView(
    CsrfExemptMixin,
    JsonRequestResponseMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "hub.change_content_order"
    login_url = "account_login"
    redirect_field_name = "next"

    def handle_no_permission(self):
        return JsonResponse(
            {"error": "You do not have permission to change the content order."},
            status=403,
        )

    def post(self, request):
        for content_id, order in self.request_json.items():
            Content.objects.filter(id=content_id).update(order=order)
        return self.render_json_response({"saved": "OK"})


@login_required
def global_search(request):
    form = SearchForm()
    query = None
    results = []

    user_role = request.user.role

    if "query" in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data["query"]

            pages = Page.objects.annotate(
                search=SearchVector("title_en", "title_uk")
            ).filter(search=query)

            sections = Section.objects.annotate(
                search=SearchVector("title_en", "title_uk")
            ).filter(search=query)

            text_content = Text.objects.annotate(
                search=SearchVector(
                    "title",
                    "content_en",
                    "content_uk",
                    "content_draft_en",
                    "content_draft_uk",
                )
            ).filter(search=query)

            file_content = File.objects.annotate(search=SearchVector("title")).filter(
                search=query
            )

            image_content = Image.objects.annotate(
                search=SearchVector(
                    "title",
                )
            ).filter(search=query)

            video_content = Video.objects.annotate(
                search=SearchVector("title", "content", "content_draft")
            ).filter(search=query)

            url_content = URL.objects.annotate(
                search=SearchVector("title", "content", "content_draft")
            ).filter(search=query)

            divisions = Division.objects.annotate(
                search=SearchVector("title_en", "title_uk")
            ).filter(search=query)

            branches = Branch.objects.annotate(
                search=SearchVector("title_en", "title_uk", "address_en", "address_uk")
            ).filter(search=query)

            persons = Person.objects.annotate(
                search=SearchVector(
                    "first_name_en", "last_name_en", "first_name_uk", "last_name_uk"
                )
            ).filter(search=query)

            if user_role == CustomUser.Role.OWNER:
                donors = (
                    Donor.objects.annotate(
                        search=SearchVector("first_name", "last_name", "email")
                    )
                    .filter(search=query)
                    .distinct()
                )

                donations = Donation.objects.annotate(
                    search=SearchVector("transaction_id")
                ).filter(search=query)
            else:
                donors = []
                donations = []

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
                + list(donors)
                + list(donations)
            )

    return render(
        request,
        "hub/global_search.html",
        {
            "form": form,
            "query": query,
            "results": results,
        },
    )
