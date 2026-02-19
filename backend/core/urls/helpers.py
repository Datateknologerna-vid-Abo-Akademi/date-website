from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView


def legacy_template_routes_enabled() -> bool:
    return bool(getattr(settings, "LEGACY_TEMPLATE_ROUTES_ENABLED", True))


def app_enabled(app_label: str) -> bool:
    """Return True when an app label exists in INSTALLED_APPS."""
    for installed_app in settings.INSTALLED_APPS:
        if installed_app == app_label or installed_app.startswith(f"{app_label}."):
            return True
    return False


def optional_include(prefix: str, urlconf: str, app_label: str):
    if not legacy_template_routes_enabled():
        return []
    if not app_enabled(app_label):
        return []
    return [path(prefix, include(urlconf))]


def optional_members_includes(prefix: str = "members/", include_auth_urls: bool = True):
    if not legacy_template_routes_enabled():
        return []
    if not app_enabled("members"):
        return []

    patterns = [path(prefix, include("members.urls"))]
    if include_auth_urls:
        patterns.append(path(prefix, include("django.contrib.auth.urls")))
    return patterns


def legacy_index(legacy_view):
    if legacy_template_routes_enabled():
        return legacy_view
    return RedirectView.as_view(url=getattr(settings, "FRONTEND_DEFAULT_ROUTE", "/"), permanent=False)
