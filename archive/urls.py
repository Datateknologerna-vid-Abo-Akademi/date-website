from django.urls import path
from django.conf.urls import url
from . import views


app_name = 'archive'

urlpatterns = [
    # /archive/
    path('', views.index, name='index'),
    # /archive/<Collection_id>/
    url(r'^(?P<pk>[0-9]+)/$', views.DetailView.as_view(), name='detail'),
    path('upload/', views.upload, name='upload'),

]

