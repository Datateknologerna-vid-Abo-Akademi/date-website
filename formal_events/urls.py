from django.urls import path

from . import views

app_name = 'formal_events'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<slug:slug>/', views.DetailView.as_view(), name='detail'),
    path('<slug:slug>/<slug:static_slug>/', views.static_view, name='staticpage'),
    #TODO GENERATE PATHS WITH EVENT SLUG
]