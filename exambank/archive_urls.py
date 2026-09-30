from django.urls import path

from . import views

app_name = 'archive'

urlpatterns = [
    path('exams/', views.exams_index, name='exams'),
    path('exams/<int:pk>/', views.FilteredExamsListView.as_view(), name='exams_detail'),
    path('exam-upload/<int:pk>/', views.exam_upload, name='exam_upload'),
    path('exam-archive-upload/', views.exam_archive_upload, name='exam_archive_upload'),
]
