from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'archive'

urlpatterns = [
    # New pictures
    path('pictures/', login_required(views.year_index), name='years'),
    # /archive/pictures/<year>/
    path('pictures/<int:year>/', login_required(views.picture_index), name='pictures'),
    path('pictures/<int:year>/<str:album>/', login_required(views.picture_detail), name='detail'),
    # /documents/
    path('documents/', login_required(views.FilteredDocumentsListView.as_view()), name='documents'),
    path('exams/', login_required(views.exams_index), name='exams'),
    path('exams/<int:pk>/', login_required(views.FilteredExamsListView.as_view()), name='exams_detail'),
    path('exam-upload/<int:pk>/', login_required(views.exam_upload), name='exam_upload'),
    path('exam-archive-upload/', login_required(views.exam_archive_upload), name='exam_archive_upload'),
    path('picture-upload/<int:collection_id>/', views.picture_upload, name='picture_upload'),
    path('picture-upload/direct/', views.picture_upload_direct, name='picture_upload_direct'),
    path('picture-upload/fallback/', views.picture_upload_fallback, name='picture_upload_fallback'),
    path('picture-upload/complete/', views.picture_upload_complete, name='picture_upload_complete'),
    path('upload/', login_required(views.upload), name='upload'),
    path('cleanMedia/', login_required(views.clean_media), name='cleanMedia'),

]
