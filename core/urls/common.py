from django.urls import include, path

from homepage import views as homepage_views


def build_urlpatterns(*localized_patterns):
    return [
        *localized_patterns,
        path("set_lang/", homepage_views.set_language, name="set_lang"),
    ]
