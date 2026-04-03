"""URL configuration for the pulterit site."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from homepage import views as homepage
from core.urls.common import build_urlpatterns

app_name = 'core'

urlpatterns = build_urlpatterns(
    path('', homepage.index, name='index'),
    path('news/', include('news.urls')),
    path('members/', include('members.urls')),
    path('members/', include('django.contrib.auth.urls')),
    path('events/', include('events.urls')),
    path('pages/', include('staticpages.urls')),
    path('ads/', include('ads.urls')),
    path('social/', include('social.urls')),
    path('polls/', include('polls.urls')),
    path('admin/', admin.site.urls),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('publications/', include('publications.urls')),
)

if getattr(settings, 'ARCHIVE_ENABLED', True):
    urlpatterns[0].url_patterns.insert(4, path('archive/', include('archive.urls')))

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = homepage.handler404
handler500 = homepage.handler500
