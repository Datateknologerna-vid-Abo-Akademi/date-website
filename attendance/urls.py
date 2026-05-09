from django.urls import path

from . import views

urlpatterns = [
    path("", views.AttendanceEventsView.as_view(), name="attendance-index"),
    path("<slug:slug>/", views.AttendanceEventDetailView.as_view(), name="attendance-event-view"),
    path("<slug:slug>/overview", views.AttendanceEventOverview.as_view(), name="attendance-event-overview")
]
