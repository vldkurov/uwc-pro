import logging
import uuid
from itertools import groupby

from braces.views import CsrfExemptMixin, JsonRequestResponseMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import FieldError, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils import translation
from django.utils.translation import get_language
from django.views.generic import ListView, View
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import CreateView, UpdateView, DeleteView, ModelFormMixin
from django.db import transaction

from .forms import BranchForm, PersonForm, PhoneFormSet, EmailFormSet, DivisionForm
from .models import Branch, Division, Person

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

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     slug = self.kwargs.get("slug")
    #     current_division = (
    #         get_object_or_404(Division, slug=slug) if slug else Division.objects.first()
    #     )
    #     context["current_division"] = current_division
    #
    #     religious_keywords = ["Church", "Церква", "Церкви", "Parish", "Парафія"]
    #
    #     is_religious = any(
    #         keyword.lower() in current_division.title.lower()
    #         for keyword in religious_keywords
    #     )
    #     context["is_religious"] = is_religious
    #
    #     current_language = translation.get_language() or "en"
    #
    #     sort_column = self.request.GET.get("sort", "title")
    #     sort_direction = self.request.GET.get("direction", "asc")
    #
    #     if sort_column == "title":
    #         sort_column = f"title_{current_language}"
    #
    #     sort_order = f"-{sort_column}" if sort_direction == "desc" else sort_column
    #
    #     branches = current_division.branches.all().order_by(sort_order)
    #
    #     context["branches"] = branches
    #     context["current_base_sort"] = self.request.GET.get("sort", "title")
    #     context["current_direction"] = sort_direction
    #
    #     return context

    def get_context_data(self, **kwargs):

        if not Division.objects.exists():
            return redirect("locations:division_create")

        context = super().get_context_data(**kwargs)
        slug = self.kwargs.get("slug")
        current_division = (
            get_object_or_404(Division, slug=slug) if slug else Division.objects.first()
        )
        context["current_division"] = current_division

        religious_keywords = ["Church", "Церква", "Церкви", "Parish", "Парафія"]

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

        try:
            branches = current_division.branches.all().order_by(sort_order)
        except FieldError:
            branches = current_division.branches.all().order_by("title")

        context["branches"] = branches
        context["current_base_sort"] = self.request.GET.get("sort", "title")
        context["current_direction"] = sort_direction

        return context


# class DivisionCreateView(DivisionMixin, TrackUserMixin, CreateView):
#     fields = ["title_en", "title_uk"]
#     template_name = "locations/manage/division/form.html"
#     login_url = "account_login"
#     redirect_field_name = "next"
#     permission_required = "locations.add_division"


class DivisionCreateView(DivisionMixin, TrackUserMixin, CreateView):
    model = Division
    form_class = DivisionForm
    template_name = "locations/manage/division/form.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.add_division"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse("locations:division_list", kwargs={"slug": self.object.slug})


class DivisionUpdateView(DivisionMixin, TrackUserMixin, UpdateView):
    form_class = DivisionForm
    template_name = "locations/manage/division/form.html"
    permission_required = "locations.change_division"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse("locations:division_list", kwargs={"slug": self.object.slug})


class DivisionDeleteView(DivisionMixin, DeleteView):
    template_name = "locations/manage/division/delete.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.delete_division"


# class DivisionOrderView(
#     CsrfExemptMixin,
#     JsonRequestResponseMixin,
#     DivisionMixin,
#     View,
# ):
#     login_url = "account_login"
#     redirect_field_name = "next"
#     permission_required = "locations.change_division_order"
#
#     def handle_no_permission(self):
#         return JsonResponse(
#             {"error": "You do not have permission to change the Division order."},
#             status=403,
#         )
#
#     def post(self, request):
#         for division_id, order in self.request_json.items():
#             Division.objects.filter(id=division_id).update(order=order)
#         return self.render_json_response({"saved": "OK"})


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
        try:
            # Validate incoming JSON data
            data = self.request_json

            # Validate that each key is a valid UUID
            with transaction.atomic():  # Ensure atomicity
                for division_id, order in data.items():
                    try:
                        # Validate UUID
                        uuid.UUID(division_id)
                        # Update the order
                        Division.objects.filter(id=division_id).update(order=order)
                    except (ValueError, ValidationError):
                        # Invalid UUID or order
                        return JsonResponse(
                            {"error": f"Invalid ID: {division_id}"}, status=400
                        )

            # Success response
            return self.render_json_response({"saved": "OK"})

        except Exception as e:
            # Catch any unexpected errors
            return JsonResponse({"error": str(e)}, status=400)


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

        religious_keywords = ["Church", "Церква", "Церкви", "Parish", "Парафія"]

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
        phone_formset = PhoneFormSet(instance=self.branch)
        email_formset = EmailFormSet(instance=self.branch)

        return self.render_to_response(
            {
                "branch_form": branch_form,
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
        phone_formset = PhoneFormSet(request.POST, instance=self.branch)
        email_formset = EmailFormSet(request.POST, instance=self.branch)

        is_valid = True

        if not branch_form.is_valid():
            is_valid = False
            print("Branch form validation failed:")
            print(branch_form.errors)

        if not phone_formset.is_valid():
            is_valid = False
            print("Phone formset validation failed:")
            print(phone_formset.errors)

        if not email_formset.is_valid():
            is_valid = False
            print("Email formset validation failed:")
            print(email_formset.errors)

        # if is_valid:
        #     branch = branch_form.save(commit=False)
        #     branch.division = self.division
        #
        #     branch.save()
        #     phone_formset.save()
        #     email_formset.save()
        #
        #     return redirect("locations:division_list", slug=self.division.slug)

        if is_valid:
            # Save the branch first
            branch = branch_form.save(commit=False)
            branch.division = self.division
            branch.save()  # Save the branch before saving related formsets

            # Assign branch instance to formsets
            phone_formset.instance = branch
            email_formset.instance = branch

            # Save formsets
            phone_formset.save()
            email_formset.save()

            return redirect("locations:division_list", slug=self.division.slug)

        return self.render_to_response(
            {
                "branch_form": branch_form,
                "phone_formset": phone_formset,
                "email_formset": email_formset,
                "division": self.division,
                "is_religious": self.is_religious,
            }
        )


class BranchDeleteView(DivisionMixin, DeleteView):
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


class BranchDisplayView(DivisionMixin, View):
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


class BranchHideView(DivisionMixin, View):
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


class PersonListView(DivisionMixin, ListView):
    model = Person
    context_object_name = "persons"
    template_name = "locations/manage/person/list.html"
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.view_person"

    def get_queryset(self):
        language = get_language()
        if language == "uk":
            sort_field = "last_name_uk"
        else:
            sort_field = "last_name_en"

        queryset = Person.objects.all().order_by(sort_field)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        language = get_language()
        sort_field = "last_name_uk" if language == "uk" else "last_name_en"

        grouped = {}
        for key, group in groupby(
            queryset, key=lambda x: getattr(x, sort_field)[0].upper()
        ):
            grouped[key] = list(group)

        context["grouped_persons"] = grouped
        return context


class PersonCreateView(DivisionMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = "locations/manage/person/form.html"
    success_url = reverse_lazy("locations:division_redirect")
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.add_person"


class PersonUpdateView(DivisionMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = "locations/manage/person/form.html"
    success_url = reverse_lazy("locations:division_redirect")
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.change_person"


class PersonDeleteView(DivisionMixin, DeleteView):
    model = Person
    template_name = "locations/manage/person/delete.html"
    success_url = reverse_lazy("locations:person_list")
    login_url = "account_login"
    redirect_field_name = "next"
    permission_required = "locations.delete_person"
