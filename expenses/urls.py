from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list, name='list'),
    path('new/', views.expense_create, name='create'),
    path('<int:pk>/', views.expense_detail, name='detail'),
    path('<int:pk>/pdf/', views.download_pdf, name='pdf'),
    path('receipt/<int:pk>/', views.receipt_file, name='receipt'),
]
