from django.urls import include, path

from date import views as date_views


def build_urlpatterns(*localized_patterns):
    return [
        path("healthz/", date_views.healthz, name="healthz"),
        path("readyz/", date_views.readyz, name="readyz"),
        *localized_patterns,
        path("set_lang/", date_views.set_language, name="set_lang"),
    ]
