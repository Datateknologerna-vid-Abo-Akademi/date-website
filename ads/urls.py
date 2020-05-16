from django.urls import path
from . import views

app_name = 'ads'

urlpatterns = [
    path('update/', views.igUrl, name='igurl'),
    path('', views.adsIndex, name='index'),

]
