import os

from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'archive'

s3_urls = []

if os.getenv('USE_S3'):
    s3_urls = [
    # Old pictures
    path('old/', login_required(views.old_year_index), name='old'),
    # /archive/old/<year>/
    path('old/<int:year>/', login_required(views.old_picture_index), name='old_pictures'),
    # /archive/pictures/<year>/<album_name>/
    path('old/<int:year>/<str:album>/', login_required(views.old_detail), name='old_detail'),
    ]

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

urlpatterns.extend(s3_urls)