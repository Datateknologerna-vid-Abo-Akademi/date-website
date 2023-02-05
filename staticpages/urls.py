from django.urls import path, re_path

from . import views

app_name = 'staticpages'

urlpatterns = [
    path('index/', views.StaticPageIndex.as_view(), name='index'),
    path('urls/', views.staticUrl, name='urls'),
    re_path(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='page'),
]
