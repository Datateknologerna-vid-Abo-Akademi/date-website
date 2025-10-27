"""Biocum URL Configuration.

The `urlpatterns` list routes URLs to views.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from date import views as date

app_name = 'core'

urlpatterns = [
    path('', date.index, name='index'),
    path('news/', include('news.urls')),
    path('members/', include('members.urls')),
    path('members/', include('django.contrib.auth.urls')),
    path('archive/', include('archive.urls')),
    path('events/', include('events.urls')),
    path('pages/', include('staticpages.urls')),
    path('ads/', include('ads.urls')),
    path('social/', include('social.urls')),
    path('polls/', include('polls.urls')),
    path('admin/', admin.site.urls),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = date.handler404
handler500 = date.handler500
