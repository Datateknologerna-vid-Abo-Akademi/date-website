from django.urls import re_path

from . import views

app_name = 'staticpages'

urlpatterns = [
    re_path(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='page'),
]
