from django.urls import re_path

from . import feed, views

app_name = 'events'

urlpatterns = [
    re_path(r'^$', views.IndexView.as_view(), name='index'),
    re_path(r'^my/$', views.MySignupsView.as_view(), name='my-signups'),
    re_path(r'^edit/(?P<token>[0-9a-f-]+)/$', views.EventEditSignupView.as_view(), name='edit-signup'),
    re_path(r'^(?P<slug>[-\w]+)/$', views.EventDetailView.as_view(), name='detail'),
    re_path(r'^feed$', feed.EventFeed(), name='feed'),
]
