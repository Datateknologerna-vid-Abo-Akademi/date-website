from django.urls import path

from . import views

app_name = 'members'

urlpatterns = [
    path('info/', views.EditView.as_view(), name='info'),
]
