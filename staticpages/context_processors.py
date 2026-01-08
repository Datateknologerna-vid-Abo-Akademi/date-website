from django.core.cache import cache

from .models import StaticPageNav, StaticUrl

NAV_CACHE_TIMEOUT = 60
URL_CACHE_TIMEOUT = 60


def get_categories(context):
    categories = cache.get_or_set(
        'staticpages_nav_categories',
        lambda: list(StaticPageNav.objects.all().order_by('nav_element')),
        NAV_CACHE_TIMEOUT
    )
    return {'categories': categories}


def get_urls(context):
    urls = cache.get_or_set(
        'staticpages_nav_urls',
        lambda: list(StaticUrl.objects.all().order_by('dropdown_element')),
        URL_CACHE_TIMEOUT
    )
    return {'urls': urls}
