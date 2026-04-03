import django.views.generic
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from . import two_factor
from . import views

app_name = 'members'

urlpatterns = [
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('login/', two_factor.MemberLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('password_change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('info/', views.UserinfoView.as_view(), name='info'),
    path('cert/', views.CertificateView.as_view(), name='certificate'),
    path('funktionar/', views.FunctionaryView.as_view(), name='functionary'),
    path('funktionarer/', views.FunctionariesView.as_view(), name='functionaries'),
]

if getattr(settings, 'MEMBERS_SIGNUP_ENABLED', True):
    urlpatterns.insert(0, re_path(r'^signup/$', views.signup, name='signup'))

if "alumni" in settings.INSTALLED_APPS:
    urlpatterns += [path('alumn/signup', django.views.generic.RedirectView.as_view(url='/alumni/signup/', permanent=True), name='alumni_signup'),]
