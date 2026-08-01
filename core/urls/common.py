from django.urls import path
from django.views.i18n import JavaScriptCatalog

from date import views as date_views


def build_urlpatterns(*localized_patterns):
    return [
        path("healthz/", date_views.healthz, name="healthz"),
        path("readyz/", date_views.readyz, name="readyz"),
        *localized_patterns,
        path("set_lang/", date_views.set_language, name="set_lang"),
        path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    ]
