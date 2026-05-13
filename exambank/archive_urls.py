from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'archive'

urlpatterns = [
    path('exams/', login_required(views.exams_index), name='exams'),
    path('exams/<int:pk>/', login_required(views.FilteredExamsListView.as_view()), name='exams_detail'),
    path('exam-upload/<int:pk>/', login_required(views.exam_upload), name='exam_upload'),
    path('exam-archive-upload/', login_required(views.exam_archive_upload), name='exam_archive_upload'),
]
