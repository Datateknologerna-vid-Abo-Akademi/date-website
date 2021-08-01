from django.urls import path
from django.conf.urls import url
from . import views
from django.contrib.auth.decorators import login_required

app_name = 'archive'

urlpatterns = [
    # New pictures
    path('pictures/', login_required(views.year_index), name='years'),
    # /archive/pictures/<year>/
    path('pictures/<int:year>/', login_required(views.picture_index), name='pictures'),
    # /archive/pictures/<year>/<Collection_id>/
    path('pictures/<int:year>/<str:album>/', login_required(views.picture_detail), name='detail'),
    # /documents/
    path('documents/', login_required(views.FilteredDocumentsListView.as_view()), name='documents'),
    path('upload/', login_required(views.upload), name='upload'),
    path('cleanMedia/', login_required(views.clean_media), name='cleanMedia'),

]