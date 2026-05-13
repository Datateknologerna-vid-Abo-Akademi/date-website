from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views
from exambank import views as exambank_views
from gallery import views as gallery_views

app_name = 'archive'

urlpatterns = [
    # New pictures
    path('pictures/', login_required(gallery_views.year_index), name='years'),
    # /archive/pictures/<year>/
    path('pictures/<int:year>/', login_required(gallery_views.picture_index), name='pictures'),
    # /archive/pictures/<year>/<album>/
    path('pictures/<int:year>/<str:album>/', login_required(gallery_views.picture_detail), name='detail'),
    # /documents/
    path('documents/', login_required(views.FilteredDocumentsListView.as_view()), name='documents'),
    path('exams/', exambank_views.exams_index, name='exams'),
    path('exams/<int:pk>/', exambank_views.FilteredExamsListView.as_view(), name='exams_detail'),
    path('exam-upload/<int:pk>/', exambank_views.exam_upload, name='exam_upload'),
    path('exam-archive-upload/', exambank_views.exam_archive_upload, name='exam_archive_upload'),
    path('upload/', login_required(gallery_views.upload), name='upload'),
    path('cleanMedia/', login_required(views.clean_media), name='cleanMedia'),

]
