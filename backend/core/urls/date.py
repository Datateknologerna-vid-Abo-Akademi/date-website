from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from date import views as date

from .helpers import legacy_index, optional_include, optional_members_includes

urlpatterns = [
    *optional_include("admin/", "admin_ordering.urls", "admin_ordering"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("api.urls")),
    path("", legacy_index(date.index), name="index"),
    *optional_include("ckeditor5/", "django_ckeditor_5.urls", "django_ckeditor_5"),
    *optional_members_includes(prefix="members/", include_auth_urls=True),
    *optional_include('archive/', 'archive.urls', 'archive'),
    *optional_include('events/', 'events.urls', 'events'),
    *optional_include('pages/', 'staticpages.urls', 'staticpages'),
    *optional_include('ads/', 'ads.urls', 'ads'),
    *optional_include('social/', 'social.urls', 'social'),
    *optional_include('news/', 'news.urls', 'news'),
    *optional_include('polls/', 'polls.urls', 'polls'),
    *optional_include('ctf/', 'ctf.urls', 'ctf'),
    *optional_include('publications/', 'publications.urls', 'publications'),
    *optional_include('alumni/', 'alumni.urls', 'alumni'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = date.handler404
handler500 = date.handler500
