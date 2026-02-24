from django.urls import path

from . import views

urlpatterns = [
    path("", views.AttendanceEventsView.as_view(), name="index"),
    path("<slug:slug>/", views.AttendanceEventDetailView.as_view(), name="attendance-event-view")
]
