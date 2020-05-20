from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    path('update/', views.igUrls, name='igurl'),
    path('', views.socialIndex, name='index'),

]
