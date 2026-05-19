from django.conf import settings
from django.db.models import Prefetch, Q

from .models import StaticPageNav, StaticUrl


def _visible_urls_queryset(user=None):
    queryset = StaticUrl.objects.all()
    if not getattr(settings, "ARCHIVE_ENABLED", True):
        if "exambank" in settings.INSTALLED_APPS:
            queryset = queryset.exclude(Q(url__startswith="/archive/") & ~Q(url__startswith="/archive/exams/"))
        else:
            queryset = queryset.exclude(url__startswith="/archive/")
    if user is not None and not user.is_authenticated:
        queryset = queryset.exclude(logged_in_only=True)
    return queryset


def _filtered_urls_queryset(request=None):
    user = getattr(request, "user", None)
    children_queryset = _visible_urls_queryset(user).select_related("category").order_by("dropdown_element")
    return (
        _visible_urls_queryset(user)
        .filter(parent=None)
        .select_related("category")
        .prefetch_related(Prefetch("children", queryset=children_queryset))
        .order_by("dropdown_element")
    )


def get_categories(request):
    filtered_urls = _filtered_urls_queryset(request)
    visible_category_ids = set(filtered_urls.values_list("category_id", flat=True))
    categories = StaticPageNav.objects.all().order_by("nav_element")
    if not getattr(settings, "ARCHIVE_ENABLED", True):
        if "exambank" in settings.INSTALLED_APPS:
            categories = categories.exclude(
                Q(use_category_url=True) & Q(url__startswith="/archive/") & ~Q(url__startswith="/archive/exams/")
            )
        else:
            categories = categories.exclude(use_category_url=True, url__startswith="/archive/")
    categories = [
        category for category in categories if category.use_category_url or category.id in visible_category_ids
    ]
    return {"categories": categories}


def get_urls(request):
    return {"urls": _filtered_urls_queryset(request)}
