import django.views.generic
from django.conf import settings
from django.urls import include, path, re_path

from . import views

app_name = 'members'

urlpatterns = [
    re_path(r'^signup/$', views.signup, name='signup'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('password_reset/', views.CustomPasswordResetView.as_view(),
         name='password_reset'),
    re_path('^', include('django.contrib.auth.urls')),
    path('password_change/', views.CustomPasswordChangeView.as_view(),
         name='custom_password_change'),
    path('info/', views.UserinfoView.as_view(), name='info'),
    path('cert/', views.CertificateView.as_view(), name='certificate'),
    path('funktionar/', views.FunctionaryView.as_view(), name='functionary'),
    path('funktionarer/', views.FunctionariesView.as_view(), name='functionaries'),
]

if "alumni" in settings.INSTALLED_APPS:
    urlpatterns += [path('alumn/signup', django.views.generic.RedirectView.as_view(
        url='/alumni/signup/', permanent=True), name='alumni_signup'),]
