from django.urls import re_path
from django.views.decorators.cache import cache_page

from . import feed, views

app_name = 'events'

urlpatterns = [
    re_path(r'^$', cache_page(60)(views.IndexView.as_view()), name='index'),
    re_path(r'^(?P<slug>[-\w]+)/$', views.EventDetailView.as_view(), name='detail'),
    re_path(r'^feed$', feed.EventFeed(), name='feed'),
]
