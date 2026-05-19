from django.urls import path

from . import views

app_name = "exambank"

urlpatterns = [
    path("", views.exams_index, name="exams"),
    path("<int:pk>/", views.FilteredExamsListView.as_view(), name="exams_detail"),
    path("upload/<int:pk>/", views.exam_upload, name="exam_upload"),
    path("archive-upload/", views.exam_archive_upload, name="exam_archive_upload"),
]
