from django.urls import path

from . import views

app_name = 'lucia'

urlpatterns = [
    path('', views.index, name='index'),
    path('<slug:slug>/', views.candidate, name='candidate'),
]
