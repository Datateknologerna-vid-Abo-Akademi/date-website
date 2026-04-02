from django.conf import settings

from .models import StaticPageNav, StaticUrl


def _is_enabled_url(url: str) -> bool:
    if getattr(settings, 'ARCHIVE_ENABLED', True):
        return True

    return not url.startswith('/archive/')


def get_categories(context):
    filtered_urls = [
        url for url in StaticUrl.objects.select_related('category').all()
        if _is_enabled_url(url.url)
    ]
    visible_category_ids = {url.category_id for url in filtered_urls}
    categories = [
        category for category in StaticPageNav.objects.all().order_by('nav_element')
        if (category.use_category_url and _is_enabled_url(category.url))
        or (not category.use_category_url and category.id in visible_category_ids)
    ]
    return {'categories': categories}


def get_urls(context):
    urls = [
        url for url in StaticUrl.objects.all().order_by('dropdown_element')
        if _is_enabled_url(url.url)
    ]
    return {'urls': urls}
