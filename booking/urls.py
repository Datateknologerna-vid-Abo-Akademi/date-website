from django.urls import path

from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.RoomListView.as_view(), name='index'),
    path('<int:pk>/', views.room_detail, name='room_detail'),
]
