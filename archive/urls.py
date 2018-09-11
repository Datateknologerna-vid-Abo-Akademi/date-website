from django.urls import path
from . import views

urlpatterns = [
    path('', views.showroom, name='allFiles'),
    path('upload/', views.upload, name='upload'),
]

