from django.conf.urls import url
from django.urls import path

from . import views

app_name = 'staticpages'

urlpatterns = [
    url('index/', views.StaticPageIndex.as_view(), name='index'),
    path('urls/', views.staticUrl, name='urls'),
    url(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='page'),
]
