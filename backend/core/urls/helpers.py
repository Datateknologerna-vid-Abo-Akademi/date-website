from django.conf import settings
from django.urls import include, path


def app_enabled(app_label: str) -> bool:
    """Return True when an app label exists in INSTALLED_APPS."""
    for installed_app in settings.INSTALLED_APPS:
        if installed_app == app_label or installed_app.startswith(f"{app_label}."):
            return True
    return False


def optional_include(prefix: str, urlconf: str, app_label: str):
    if not app_enabled(app_label):
        return []
    return [path(prefix, include(urlconf))]


def optional_members_includes(prefix: str = "members/", include_auth_urls: bool = True):
    if not app_enabled("members"):
        return []

    patterns = [path(prefix, include("members.urls"))]
    if include_auth_urls:
        patterns.append(path(prefix, include("django.contrib.auth.urls")))
    return patterns
