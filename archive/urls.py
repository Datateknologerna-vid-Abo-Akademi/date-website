from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'archive'

urlpatterns = [
    path('pictures/', login_required(views.year_index), name='years'),
    # /archive/pictures/<year>/
    path('pictures/<int:year>/', login_required(views.picture_index), name='pictures'),
    # /archive/pictures/<year>/<Collection_id>/
    path('pictures/<int:year>/<int:pk>/', login_required(views.DetailView.as_view()), name='detail'),
    # /documents/
    path('documents/', login_required(views.FilteredDocumentsListView.as_view()), name='documents'),
    path('upload/', login_required(views.upload), name='upload'),
    path('cleanMedia/', login_required(views.clean_media), name='cleanMedia'),

]