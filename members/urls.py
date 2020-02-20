from django.conf.urls import url
from django.urls import path, include

from . import views

app_name = 'members'

urlpatterns = [
    url(r'^signup/$', views.signup, name='signup'),
    url(r'^activate/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        views.activate, name='activate'),
    url('^', include('django.contrib.auth.urls')),
    path('info/', views.EditView.as_view(), name='info'),
]
