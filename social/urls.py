from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    path('', views.socialIndex, name='index'),
    path('harassment/', views.harassment_form, name='harassment'),
]
