from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, ModelFormMixin
from braces.views import CsrfExemptMixin, JsonRequestResponseMixin

from locations.models import Division


class TrackUserMixin(ModelFormMixin, View):
    def form_valid(self, form):
        if self.request.method == "POST" and not getattr(self, "object", None):
            form.instance.created_by = self.request.user
        elif self.request.method == "POST":
            form.instance.updated_by = self.request.user
        return super().form_valid(form)


class DivisionMixin(LoginRequiredMixin):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs.get("slug")
        if slug:
            context["current_division"] = get_object_or_404(Division, slug=slug)
        else:
            context["current_division"] = Division.objects.first()
        return context


class DivisionCreateView(DivisionMixin, TrackUserMixin, CreateView):
    fields = ["title_en", "title_uk"]
    template_name = "locations/manage/division/form.html"


class DivisionUpdateView(DivisionMixin, TrackUserMixin, UpdateView):
    fields = ["title_en", "title_uk"]
    template_name = "locations/manage/division/form.html"


class DivisionDeleteView(DivisionMixin, DeleteView):
    template_name = "locations/manage/division/delete.html"


class DivisionOrderView(
    CsrfExemptMixin,
    JsonRequestResponseMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "hub.change_division_order"
    login_url = "account_login"
    redirect_field_name = "next"

    def handle_no_permission(self):
        return JsonResponse(
            {"error": "You do not have permission to change the Division order."},
            status=403,
        )

    def post(self, request):
        for division_id, order in self.request_json.items():
            Division.objects.filter(id=division_id).update(order=order)
        return self.render_json_response({"saved": "OK"})


class BranchDetailView(DetailView):
    pass
