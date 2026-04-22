from django.conf import settings

from .models import StaticPageNav, StaticUrl


def _filtered_urls_queryset():
    queryset = StaticUrl.objects.select_related('category').order_by('dropdown_element')
    if getattr(settings, 'ARCHIVE_ENABLED', True):
        return queryset
    return queryset.exclude(url__startswith='/archive/')


def _filtered_urls(request):
    if not hasattr(request, "_staticpages_filtered_urls"):
        request._staticpages_filtered_urls = list(_filtered_urls_queryset())
    return request._staticpages_filtered_urls


def get_categories(request):
    filtered_urls = _filtered_urls(request)
    visible_category_ids = {url.category_id for url in filtered_urls}
    categories = StaticPageNav.objects.all().order_by('nav_element')
    if not getattr(settings, 'ARCHIVE_ENABLED', True):
        categories = categories.exclude(use_category_url=True, url__startswith='/archive/')
    categories = [
        category for category in categories
        if category.use_category_url or category.id in visible_category_ids
    ]
    return {'categories': categories}


def get_urls(request):
    return {'urls': _filtered_urls(request)}
