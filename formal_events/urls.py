from django.urls import path

from . import views

app_name = 'formal_events'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    #TODO GENERATE PATHS WITH EVENT SLUG
]