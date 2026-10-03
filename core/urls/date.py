"""URL configuration for the date site."""

from django.conf import settings
from django.conf.urls.static import static

from core.urls.common import build_urlpatterns
from date import views as date

app_name = 'core'

urlpatterns = build_urlpatterns(
    'index',
    'news',
    'members',
    'two_factor',
    'archive',
    'events',
    'pages',
    'ads',
    'social',
    'polls',
    'ctf',
    'admin',
    'ckeditor',
    'publications',
    'alumni',
    'attendance',
    # Room booking. Mounted only when the capability is on, so a release can
    # hide the pages without changing the installed app list.
    *(['booking'] if settings.BOOKING_ENABLED else []),
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]

handler404 = date.handler404
handler500 = date.handler500
