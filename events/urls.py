from django.conf.urls import url, include
from django.conf import settings
from . import views

app_name = 'events'

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<slug>[-\w]+)/$', views.DetailView.as_view(), name='detail'),
    url(r'^(?P<slug>[-\w]+)/attend$', views.add_event_attendance, name='attend'),
    url(r'^(?P<slug>[-\w]+)/cancel$', views.cancel_event_attendance, name='cancel'), #TODO: Remove possibility to remove attendace without rights
]
