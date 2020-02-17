from django.conf.urls import url
from django.urls import path

from . import views

app_name = 'members'

urlpatterns = [
    url(r'^signup/$', views.signup, name='signup'),
    path('info/', views.EditView.as_view(), name='info'),
]
