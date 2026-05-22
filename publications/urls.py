from django.urls import path

from . import views

app_name = 'publications'

urlpatterns = [
    path('', views.pdf_list, name='pdf_list'),
    path('<slug:collection_slug>/', views.collection_detail, name='collection_detail'),
    path('<slug:collection_slug>/<slug:slug>/', views.pdf_view, name='pdf_view'),
]
