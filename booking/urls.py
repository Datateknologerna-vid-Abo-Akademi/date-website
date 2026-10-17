from django.urls import path

from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.RoomListView.as_view(), name='index'),
    path('mine/', views.MyBookingsView.as_view(), name='my_bookings'),
    path('cancel/', views.cancel_booking, name='cancel'),
    path('<int:pk>/', views.room_detail, name='room_detail'),
]
