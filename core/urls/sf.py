"""SF URL Configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from date import views as date
from core.admin import admin_site
from core.urls.common import build_urlpatterns

app_name = 'core'

urlpatterns = build_urlpatterns(
    path('', date.index, name='index'),
    path('news/', include('news.urls')),
    path('members/', include('members.urls')),
    path('members/two-factor/', include(('members.two_factor_urls', 'two_factor'), namespace='two_factor')),
    path('archive/', include('archive.urls')),
    path('events/', include('events.urls')),
    path('pages/', include('staticpages.urls')),
    path('ads/', include('ads.urls')),
    path('social/', include('social.urls')),
    path('polls/', include('polls.urls')),
    path('admin/', admin_site.urls),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    path('publications/', include('publications.urls')),
    path('alumni/', include('alumni.urls')),
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = date.handler404
handler500 = date.handler500