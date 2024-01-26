import django
from django.contrib.auth.views import PasswordChangeDoneView, PasswordResetDoneView
from django.urls import include, path, re_path

from . import views

app_name = 'members'

urlpatterns = [
    re_path(r'^signup/$', views.signup, name='signup'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    re_path('^', include('django.contrib.auth.urls')),
    path('info/', views.UserinfoView.as_view(), name='info'),
    path('cert/', views.CertificateView.as_view(), name='certificate'),
    path('alumn/signup', views.alumni_signup , name='alumni-signup'),
    path('funktionar/', views.FunctionaryView.as_view(), name='functionary'),
    path('funktionarer/', views.FunctionariesView.as_view(), name='functionaries'),
]
