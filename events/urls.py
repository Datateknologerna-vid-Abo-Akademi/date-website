from django.urls import re_path

from . import feed, views

app_name = 'events'

urlpatterns = [
    re_path(r'^$', views.IndexView.as_view(), name='index'),
    re_path(r'^(?P<slug>[-\w]+)/$', views.EventDetailView.as_view(), name='detail'),
    re_path(r'^feed$', feed.EventFeed(), name='feed'),
]
