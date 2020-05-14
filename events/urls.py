from django.conf.urls import url
from . import views, feed

app_name = 'events'

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<slug>[-\w]+)/$', views.EventDetailView.as_view(), name='detail'),
    url(r'^feed$', feed.EventFeed(), name='feed'),
]
