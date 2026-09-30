from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils.translation import get_language

from .models import StaticPageNav, StaticUrl

# Backstop TTL; admin edits invalidate immediately via signals, so a missed
# invalidation never persists longer than this.
NAV_CACHE_TTL = 300
NAV_VERSION_KEY = "staticpages:navigation:version"


def _nav_version():
    version = cache.get(NAV_VERSION_KEY)
    if version is not None:
        return version
    # Initialize atomically and without expiry: an expiring version key could
    # reset to 1 while stale version-1 navigation entries still exist.
    cache.add(NAV_VERSION_KEY, 1, timeout=None)
    # Another process may have initialized a different value in the meantime.
    return cache.get(NAV_VERSION_KEY) or 1


def invalidate_nav_cache(**kwargs):
    # Bump the version after the transaction commits, so another request can
    # never populate the new version from pre-commit database state.
    def _bump():
        try:
            cache.incr(NAV_VERSION_KEY)
        except ValueError:
            # Missing key (e.g. after a cache flush); start at 2 so no
            # existing version-1 entry is reused.
            cache.add(NAV_VERSION_KEY, 2, timeout=None)

    transaction.on_commit(_bump)


def _visible_urls_queryset(user=None):
    queryset = StaticUrl.objects.all()
    if not getattr(settings, 'ARCHIVE_ENABLED', True):
        if 'exambank' in settings.INSTALLED_APPS:
            queryset = queryset.exclude(Q(url__startswith='/archive/') & ~Q(url__startswith='/archive/exams/'))
        else:
            queryset = queryset.exclude(url__startswith='/archive/')
    if user is not None and not user.is_authenticated:
        queryset = queryset.exclude(logged_in_only=True)
    return queryset


def _filtered_urls_queryset(request=None):
    user = getattr(request, 'user', None)
    children_queryset = _visible_urls_queryset(user).select_related('category').order_by('dropdown_element')
    return (
        _visible_urls_queryset(user)
        .filter(parent=None)
        .select_related('category')
        .prefetch_related(Prefetch('children', queryset=children_queryset))
        .order_by('dropdown_element')
    )


def _categories_for(urls_list):
    visible_category_ids = {url.category_id for url in urls_list}
    categories = StaticPageNav.objects.all().order_by('nav_element')
    if not getattr(settings, 'ARCHIVE_ENABLED', True):
        if 'exambank' in settings.INSTALLED_APPS:
            categories = categories.exclude(
                Q(use_category_url=True) & Q(url__startswith='/archive/') & ~Q(url__startswith='/archive/exams/')
            )
        else:
            categories = categories.exclude(use_category_url=True, url__startswith='/archive/')
    return [category for category in categories if category.use_category_url or category.id in visible_category_ids]


def navigation(request):
    """One navigation load per request (or per TTL for anonymous visitors).

    Combines the former get_categories + get_urls processors so the URL
    queryset is evaluated once and category visibility is derived from it.
    Cached only for anonymous users, keyed by project, language, archive
    mode, and a version that is bumped whenever StaticUrl/StaticPageNav
    change in the admin. Development uses the dummy cache, so caching is
    off there.
    """
    user = getattr(request, 'user', None)
    cache_key = None
    if user is None or not user.is_authenticated:
        cache_key = (
            f"staticpages:navigation:{settings.PROJECT_NAME}:{get_language()}:"
            f"{getattr(settings, 'ARCHIVE_ENABLED', True)}:{_nav_version()}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    urls_list = list(_filtered_urls_queryset(request))
    context = {'categories': _categories_for(urls_list), 'urls': urls_list}

    if cache_key is not None:
        cache.set(cache_key, context, NAV_CACHE_TTL)
    return context


def get_categories(request):
    return {'categories': navigation(request)['categories']}


def get_urls(request):
    return {'urls': navigation(request)['urls']}
