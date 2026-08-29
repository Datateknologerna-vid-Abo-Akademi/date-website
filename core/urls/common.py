from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

from core import uploads as uploads_views
from core.admin import admin_site
from date import views as date_views

# Shared canonical routes, keyed for capability-driven inclusion. Each entry
# is a thunk: include() imports the app's URLconf eagerly, so only the routes
# a variant requests are ever imported (apps not installed for a variant are
# never loaded).
ROUTES = {
    'index': lambda: path('', date_views.index, name='index'),
    'news': lambda: path('news/', include('news.urls')),
    'members': lambda: path('members/', include('members.urls')),
    'two_factor': lambda: path(
        'members/two-factor/', include(('members.two_factor_urls', 'two_factor'), namespace='two_factor')
    ),
    'archive': lambda: path('archive/', include('archive.urls')),
    'archive_exams': lambda: path('archive/', include('exambank.archive_urls')),
    'events': lambda: path('events/', include('events.urls')),
    'pages': lambda: path('pages/', include('staticpages.urls')),
    'ads': lambda: path('ads/', include('ads.urls')),
    'social': lambda: path('social/', include('social.urls')),
    'polls': lambda: path('polls/', include('polls.urls')),
    'ctf': lambda: path('ctf/', include('ctf.urls')),
    'admin': lambda: path('admin/', admin_site.urls),
    'ckeditor': lambda: path('ckeditor5/', include('django_ckeditor_5.urls')),
    'publications': lambda: path('publications/', include('publications.urls')),
    'alumni': lambda: path('alumni/', include('alumni.urls')),
    'lucia': lambda: path('lucia/', include('lucia.urls')),
    'klotterplanket': lambda: path('klotterplanket/', include('klotterplanket.urls')),
}


def build_urlpatterns(*routes):
    """Build the canonical URL patterns from ordered route keys.

    Shared health/readiness/language/upload routes are always included around
    the requested routes, so a shared route addition happens once.
    """
    unknown = set(routes) - set(ROUTES)
    if unknown:
        raise ValueError(f"Unknown route keys: {sorted(unknown)}")
    return [
        path("healthz/", date_views.healthz, name="healthz"),
        path("readyz/", date_views.readyz, name="readyz"),
        *(ROUTES[route]() for route in routes),
        path("set_lang/", date_views.set_language, name="set_lang"),
        path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
        path("_uploads/sign/", uploads_views.sign_upload, name="direct-upload-sign"),
    ]
