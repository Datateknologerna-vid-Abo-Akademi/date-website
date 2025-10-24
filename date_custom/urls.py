from django.urls import path
from django.contrib.auth.decorators import login_required

from . import views

app_name = 'date_custom'

urlpatterns = [path('membership_signup_request/',
                    login_required(views.MembershipSignupRequestView.as_view(), "/login"), name='membership_signup_request'),]
