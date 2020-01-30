from django.conf.urls import url
from . import views

app_name = 'staticpages'

urlpatterns = [
    url(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='staticpage'),
    # url('', views.StaticPageView.as_view(), name='staticpage'),
]
