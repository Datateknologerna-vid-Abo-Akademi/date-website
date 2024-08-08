from django.urls import path
from . import views

app_name = 'publications'

urlpatterns = [
    path('view/<int:pk>/', views.pdf_view, name='pdf_view'),
]
