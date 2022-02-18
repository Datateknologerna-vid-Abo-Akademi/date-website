from django.conf.urls import url
from django.urls import include, path

from . import views

app_name = 'members'

urlpatterns = [
    url(r'^signup/$', views.signup, name='signup'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    url('^', include('django.contrib.auth.urls')),
    path('info/', views.EditView.as_view(), name='info'),
    path('cert/', views.CertificateView.as_view(), name='certificate'),
]
