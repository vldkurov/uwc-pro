import logging

from braces.views import CsrfExemptMixin, JsonRequestResponseMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils import translation
from django.views.generic import ListView
from django.views.generic import View
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import CreateView, UpdateView, DeleteView, ModelFormMixin

from .forms import BranchForm, PersonForm, PhoneFormSet, EmailFormSet
from .models import Branch, Division

logger = logging.getLogger(__name__)


class TrackUserMixin(ModelFormMixin, View):
    def form_valid(self, form):
        if self.request.method == "POST" and not getattr(self, "object", None):
            form.instance.created_by = self.request.user
        elif self.request.method == "POST":
            form.instance.updated_by = self.request.user
        return super().form_valid(form)


class DivisionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    model = Division
    success_url = reverse_lazy("locations:division_redirect")
    login_url = "account_login"
    redirect_field_name = "next"


class DivisionRedirectView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, *args, **kwargs):
        first_division = Division.objects.order_by("order").first()
        if first_division:
            return redirect("locations:division_list", slug=first_division.slug)
        return redirect("locations:division_create")


class DivisionListView(DivisionMixin, ListView):
    context_object_name = "division_list"
    template_name = "locations/manage/division/list.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.view_division"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs.get("slug")
        current_division = (
            get_object_or_404(Division, slug=slug) if slug else Division.objects.first()
        )
        context["current_division"] = current_division

        religious_keywords = ["Church", "Церква", "Parish", "Парафія"]
        is_religious = any(
            keyword.lower() in current_division.title.lower()
            for keyword in religious_keywords
        )
        context["is_religious"] = is_religious

        current_language = translation.get_language() or "en"

        sort_column = self.request.GET.get("sort", "title")
        sort_direction = self.request.GET.get("direction", "asc")

        if sort_column == "title":
            sort_column = f"title_{current_language}"

        sort_order = f"-{sort_column}" if sort_direction == "desc" else sort_column

        branches = current_division.branches.all().order_by(sort_order)

        context["branches"] = branches
        context["current_base_sort"] = self.request.GET.get("sort", "title")
        context["current_direction"] = sort_direction

        return context


class DivisionCreateView(DivisionMixin, TrackUserMixin, CreateView):
    fields = ["title_en", "title_uk"]
    template_name = "locations/manage/division/form.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.add_division"


class DivisionUpdateView(DivisionMixin, TrackUserMixin, UpdateView):
    fields = ["title_en", "title_uk"]
    template_name = "locations/manage/division/form.html"
    permission_required = "locations.change_division"


class DivisionDeleteView(DivisionMixin, DeleteView):
    template_name = "locations/manage/division/delete.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.delete_division"


class DivisionOrderView(
    CsrfExemptMixin,
    JsonRequestResponseMixin,
    DivisionMixin,
    View,
):
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.change_division_order"

    def handle_no_permission(self):
        return JsonResponse(
            {"error": "You do not have permission to change the Division order."},
            status=403,
        )

    def post(self, request):
        for division_id, order in self.request_json.items():
            Division.objects.filter(id=division_id).update(order=order)
        return self.render_json_response({"saved": "OK"})


class BranchCreateUpdateView(DivisionMixin, TemplateResponseMixin, View):
    template_name = "locations/manage/branch/form.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.view_branch"
    division = None
    branch = None
    is_edit = False
    is_religious = False

    @staticmethod
    def get_person_form(person=None, prefix=None, data=None):
        return PersonForm(instance=person, prefix=prefix, data=data)

    def dispatch(self, request, *args, **kwargs):
        division_slug = kwargs.get("division_slug")
        self.division = get_object_or_404(Division, slug=division_slug)

        religious_keywords = ["Church", "Церква", "Parish", "Парафія"]
        self.is_religious = any(
            keyword.lower() in self.division.title.lower()
            for keyword in religious_keywords
        )

        branch_slug = kwargs.get("branch_slug")
        if branch_slug:
            self.branch = get_object_or_404(
                Branch, slug=branch_slug, division=self.division
            )
            self.is_edit = True
        else:
            self.branch = Branch(division=self.division)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        branch_form = BranchForm(instance=self.branch)
        branch_chair_form = self.get_person_form(
            person=self.branch.branch_chair, prefix="branch_chair"
        )
        parish_priest_form = self.get_person_form(
            person=self.branch.parish_priest, prefix="parish_priest"
        )
        phone_formset = PhoneFormSet(instance=self.branch)
        email_formset = EmailFormSet(instance=self.branch)

        return self.render_to_response(
            {
                "branch_form": branch_form,
                "branch_chair_form": branch_chair_form,
                "parish_priest_form": parish_priest_form,
                "phone_formset": phone_formset,
                "email_formset": email_formset,
                "division": self.division,
                "branch": self.branch,
                "is_edit": self.is_edit,
                "is_religious": self.is_religious,
            }
        )

    def post(self, request, *args, **kwargs):
        branch_form = BranchForm(request.POST, instance=self.branch)
        branch_chair_form = self.get_person_form(
            person=self.branch.branch_chair, prefix="branch_chair", data=request.POST
        )
        parish_priest_form = self.get_person_form(
            person=self.branch.parish_priest, prefix="parish_priest", data=request.POST
        )
        phone_formset = PhoneFormSet(request.POST, instance=self.branch)
        email_formset = EmailFormSet(request.POST, instance=self.branch)

        is_valid = True

        if not branch_form.is_valid():
            is_valid = False
            print("Branch form validation failed:")
            print(branch_form.errors)

        if not branch_chair_form.is_valid():
            is_valid = False
            print("Branch Chair form validation failed:")
            print(branch_chair_form.errors)

        if not parish_priest_form.is_valid():
            is_valid = False
            print("Parish Priest form validation failed:")
            print(parish_priest_form.errors)

        if not phone_formset.is_valid():
            is_valid = False
            print("Phone formset validation failed:")
            print(phone_formset.errors)

        if not email_formset.is_valid():
            is_valid = False
            print("Email formset validation failed:")
            print(email_formset.errors)

        if is_valid:
            branch = branch_form.save(commit=False)
            branch.division = self.division

            if any(branch_chair_form.cleaned_data.values()):
                branch_chair = branch_chair_form.save()
                branch.branch_chair = branch_chair
            else:
                if self.branch.branch_chair:
                    branch.branch_chair.delete()
                branch.branch_chair = None

            parish_priest = parish_priest_form.save()
            branch.parish_priest = parish_priest

            if any(parish_priest_form.cleaned_data.values()):
                parish_priest = parish_priest_form.save()
                branch.parish_priest = parish_priest
            else:
                if self.branch.parish_priest:
                    branch.parish_priest.delete()
                branch.parish_priest = None

            branch.save()
            phone_formset.save()
            email_formset.save()

            return redirect("locations:division_list", slug=self.division.slug)

        return self.render_to_response(
            {
                "branch_form": branch_form,
                "branch_chair_form": branch_chair_form,
                "parish_priest_form": parish_priest_form,
                "phone_formset": phone_formset,
                "email_formset": email_formset,
                "division": self.division,
                "is_religious": self.is_religious,
            }
        )


class BranchDeleteView(DeleteView):
    model = Branch
    template_name = "locations/manage/branch/delete.html"
    context_object_name = "branch"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.delete_branch"

    def get_object(self, queryset=None):
        queryset = self.get_queryset()
        division_slug = self.kwargs.get("division_slug")
        branch_slug = self.kwargs.get("branch_slug")
        return get_object_or_404(
            queryset, division__slug=division_slug, slug=branch_slug
        )

    def get_success_url(self):
        return reverse(
            "locations:division_list", kwargs={"slug": self.kwargs.get("division_slug")}
        )


class BranchDisplayView(View):
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.display"

    @staticmethod
    def post(request, division_slug, branch_slug):
        branch = get_object_or_404(
            Branch, slug=branch_slug, division__slug=division_slug
        )
        branch.display()
        return redirect("locations:division_list", slug=division_slug)


class BranchHideView(View):
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.hide"

    @staticmethod
    def post(request, division_slug, branch_slug):
        branch = get_object_or_404(
            Branch, slug=branch_slug, division__slug=division_slug
        )
        branch.hide()
        return redirect("locations:division_list", slug=division_slug)
