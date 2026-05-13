from django.urls import path

from . import views

app_name = 'gallery'

urlpatterns = [
    path('', views.year_index, name='years'),
    path('<int:year>/', views.picture_index, name='pictures'),
    path('<int:year>/<str:album>/', views.picture_detail, name='detail'),
]
