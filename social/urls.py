from django.urls import path

from harassment import views as harassment_views

from . import views

app_name = 'social'

urlpatterns = [
    path('', views.socialIndex, name='index'),
    path('harassment/', harassment_views.harassment_form, name='harassment'),
]
