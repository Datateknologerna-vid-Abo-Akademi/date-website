from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from .forms import FunctionaryForm
from .models import Functionary
from .selectors import (
    get_distinct_years,
    get_filtered_functionaries,
    get_functionaries_by_role,
    get_functionary_roles,
    get_selected_role,
    get_selected_year,
)


class FunctionaryView(View):
    template_name = "members/functionary.html"

    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        functionaries = Functionary.objects.filter(member=user).order_by("-year")
        form = FunctionaryForm(initial={"member": user})
        context = {
            "user": user,
            "functionaries": functionaries,
            "form": form,
        }
        return render(request, self.template_name, context)

    @method_decorator(login_required)
    def post(self, request):
        if "add_functionary" in request.POST:
            return self.add_functionary(request)
        if "delete_functionary" in request.POST:
            return self.delete_functionary(request)
        return redirect(reverse("members:functionary"))

    def add_functionary(self, request):
        form = FunctionaryForm(request.POST)
        form.instance.member = request.user
        if form.is_valid():
            form.save()
        else:
            user = request.user
            functionaries = Functionary.objects.filter(member=user).order_by("-year")
            context = {
                "user": user,
                "functionaries": functionaries,
                "form": form,
            }
            return render(request, self.template_name, context)
        return redirect(reverse("members:functionary"))

    def delete_functionary(self, request):
        functionary_id = request.POST.get("functionary_id")
        functionary = get_object_or_404(Functionary, id=functionary_id, member=request.user)
        functionary.delete()
        return redirect(reverse("members:functionary"))


class FunctionariesView(View):
    def get(self, request):
        distinct_years = get_distinct_years()
        functionary_roles = get_functionary_roles()

        selected_year, all_years = get_selected_year(request, distinct_years)
        selected_role, all_roles = get_selected_role(request, functionary_roles)
        board_functionaries = get_filtered_functionaries(selected_year, selected_role, True)
        board_functionaries_by_role = get_functionaries_by_role(board_functionaries)

        other_functionaries = get_filtered_functionaries(selected_year, selected_role, False)
        functionaries_by_role = get_functionaries_by_role(other_functionaries)

        context = {
            "board_functionaries_by_role": board_functionaries_by_role,
            "functionaries_by_role": functionaries_by_role,
            "distinct_years": distinct_years,
            "functionary_roles": functionary_roles,
            "selected_role": selected_role,
            "all_roles": all_roles,
            "selected_year": selected_year if isinstance(selected_year, int) else "Alla År",
            "all_years": all_years,
        }

        return render(request, "members/functionaries.html", context)
