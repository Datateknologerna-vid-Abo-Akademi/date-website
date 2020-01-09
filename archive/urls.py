from django.urls import path
from django.conf.urls import url
from . import views


app_name = 'archive'

urlpatterns = [
    # /pictures/
    path('pictures/', views.picture_index, name='pictures'),
    # /documents/
    path('documents/', views.document_index, name='documents'),
    # /archive/<Collection_id>/
    url(r'^(?P<pk>[0-9]+)/$', views.DetailView.as_view(), name='detail'),
    url(r'^(?P<pk>[0-9]+)/edit/$', views.edit, name='edit'),
    url(r'^(?P<collection_id>[0-9]+)/edit/remove/(?P<file_id>[0-9]+)/$', views.remove_file, name='remove_file'),
    path('upload/', views.upload, name='upload'),
    path('cleanMedia/', views.clean_media, name='cleanMedia'),

]