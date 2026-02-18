from django.urls import path
from . import views

app_name = 'publications'

urlpatterns = [
    path('', views.pdf_list, name='pdf_list'),
    path('<slug:slug>/', views.pdf_view, name='pdf_view'),
]