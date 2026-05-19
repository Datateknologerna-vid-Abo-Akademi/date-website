from collections import defaultdict

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Functionary, FunctionaryRole


def get_functionaries_by_role(functionaries):
    functionaries_by_role = defaultdict(list)

    for functionary in functionaries:
        functionaries_by_role[functionary.functionary_role].append(functionary)

    return dict(functionaries_by_role)


def get_current_year():
    return timezone.now().year


def get_selected_year(request, distinct_years):
    selected_year = get_current_year()
    all_years = False

    if request.user.is_authenticated and "year" in request.GET:
        year_param = request.GET["year"]

        if year_param == "all":
            selected_year = distinct_years
            all_years = True
        else:
            try:
                year = int(year_param)
                if 1900 <= year <= 2100:
                    selected_year = year
            except ValueError:
                pass

    return selected_year, all_years


def get_selected_role(request, functionary_roles):
    selected_role = None
    all_roles = False

    if request.user.is_authenticated and "role" in request.GET:
        role_param = request.GET["role"]

        if role_param == "all":
            selected_role = functionary_roles
            all_roles = True
        else:
            try:
                role_id = int(role_param)
            except ValueError, TypeError:
                pass
            else:
                selected_role = FunctionaryRole.objects.filter(pk=role_id).first()

    return selected_role, all_roles


def get_filtered_functionaries(year, selected_role, is_board):
    years = year if isinstance(year, (QuerySet, list, tuple, set)) else [year]
    main_filter = Q(year__in=years, functionary_role__board=is_board)

    if selected_role is not None:
        role_filter = (
            Q(functionary_role__in=selected_role)
            if isinstance(selected_role, QuerySet)
            else Q(functionary_role=selected_role)
        )
        main_filter &= role_filter

    return Functionary.objects.filter(main_filter).select_related("functionary_role", "member").order_by("-year")


def get_distinct_years():
    return Functionary.objects.values_list("year", flat=True).distinct().order_by("-year")


def get_functionary_roles():
    return FunctionaryRole.objects.all().order_by("title")
