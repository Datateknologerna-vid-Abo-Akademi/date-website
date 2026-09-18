"""Global public API root.

Each app that exposes JSON endpoints gets its own included URLconf here,
under its own namespace (e.g. `api:events:upcoming`). Included from
`core.urls.common.ROUTES['api']`, gated per association like every other
route so an association without the underlying app never imports its API
urls.
"""

from django.urls import include, path

app_name = 'api'

urlpatterns = [
    path('events/', include('events.api_urls')),
]
