from django.urls import path
from django.conf.urls import url
from . import views
from django.contrib.auth.decorators import login_required

app_name = 'archive'

urlpatterns = [
    # /pictures/
    path('pictures/', login_required(views.picture_index), name='pictures'),
    # /documents/
    path('documents/', login_required(views.FilteredDocumentsListView.as_view()), name='documents'),
    # /archive/<Collection_id>/
    url(r'^(?P<pk>[0-9]+)/$', login_required(views.DetailView.as_view()), name='detail'),
    path('upload/', login_required(views.upload), name='upload'),
    path('cleanMedia/', login_required(views.clean_media), name='cleanMedia'),

]