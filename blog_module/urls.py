from django.urls import path

from . import views

app_name = 'blog_module'

urlpatterns = [
    path('', views.index, name='index'),
    path('blogs/<slug:blog_id>/', views.detail, name='detail'),
]
