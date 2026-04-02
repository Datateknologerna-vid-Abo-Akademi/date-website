from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns

from date import views as date_views


def build_urlpatterns(*localized_patterns):
    return [
        *i18n_patterns(
            *localized_patterns,
            path("set_lang/", date_views.set_language, name="set_lang"),
            prefix_default_language=True,
        ),
    ]
