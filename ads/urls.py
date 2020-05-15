from django.conf.urls import url
from . import views

app_name = 'ads'

urlpatterns = [
    url('', views.AdsIndex.as_view(), name='index'),
]
