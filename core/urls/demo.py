"""URL configuration for the demo site."""

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
    'admin',
    'ckeditor',
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]

handler404 = date.handler404
handler500 = date.handler500
