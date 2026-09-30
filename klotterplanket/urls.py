from django.urls import path

from . import views

app_name = 'klotterplanket'
urlpatterns = [
    path('', views.index, name='index'),
]
