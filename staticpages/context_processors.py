from django.conf import settings

from .models import StaticPageNav, StaticUrl


def _filtered_urls_queryset():
    queryset = StaticUrl.objects.select_related('category').order_by('dropdown_element')
    if getattr(settings, 'ARCHIVE_ENABLED', True):
        return queryset
    return queryset.exclude(url__startswith='/archive/')


def get_categories(context):
    filtered_urls = _filtered_urls_queryset()
    visible_category_ids = set(filtered_urls.values_list('category_id', flat=True))
    categories = StaticPageNav.objects.all().order_by('nav_element')
    if not getattr(settings, 'ARCHIVE_ENABLED', True):
        categories = categories.exclude(use_category_url=True, url__startswith='/archive/')
    categories = [
        category for category in categories
        if category.use_category_url or category.id in visible_category_ids
    ]
    return {'categories': categories}


def get_urls(context):
    return {'urls': _filtered_urls_queryset()}
