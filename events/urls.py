from django.conf.urls import url, include
from django.conf import settings
from . import views

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='events_index'),
    url(r'^(?P<slug>[-\w]+)/$', views.DetailView.as_view(), name='events_detail' ),
    url(r'^(?P<slug>[-\w]+)/attend$', views.add_event_attendance, name='events_attend'),
    url(r'^(?P<slug>[-\w]+)/cancel$', views.cancel_event_attendance, name='events_cancel'), #TODO: Remove possibility to remove attendace without rights
]
