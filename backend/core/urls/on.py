from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.urls.helpers import legacy_index, optional_include, optional_members_includes
from events import views as events
from date import views as date

app_name = 'core'

urlpatterns = [
    path('api/v1/', include('api.urls')),
    path('', legacy_index(events.IndexView.as_view()), name='index'),
    path('admin/', admin.site.urls),
    *optional_include('', 'events.urls', 'events'),
    *optional_include('pages/', 'staticpages.urls', 'staticpages'),
    *optional_members_includes(prefix='users/', include_auth_urls=False),
    *optional_include("ckeditor5/", 'django_ckeditor_5.urls', 'django_ckeditor_5'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = date.handler404
handler500 = date.handler500
