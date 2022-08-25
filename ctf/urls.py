from django.urls import path
from django.contrib.auth.decorators import login_required

from . import views

app_name = 'ctf'
urlpatterns = [
    path('', login_required(views.IndexView.as_view()), name='index'),
    path('<slug:slug>', login_required(views.DetailView.as_view()), name='detail'),
    path('<slug:ctf_slug>/<slug:flag_slug>', login_required(views.flag), name='flag_detail'),
]