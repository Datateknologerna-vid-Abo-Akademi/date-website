from django.conf.urls import url
from . import views

app_name = 'staticpages'

urlpatterns = [
    url('index/', views.StaticPageIndex.as_view(), name='index'),
    url(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='page'),
]
