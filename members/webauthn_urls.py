from django.urls import path
from django.views.i18n import JavaScriptCatalog

from .webauthn import (
    MemberBeginAuthenticationView,
    MemberBeginRegistrationView,
    MemberCompleteAuthenticationView,
    MemberCompleteRegistrationView,
)

# Same route names as django_otp_webauthn.urls; its template tags reverse these.
app_name = 'otp_webauthn'

urlpatterns = [
    path('registration/begin/', MemberBeginRegistrationView.as_view(), name='credential-registration-begin'),
    path('registration/complete/', MemberCompleteRegistrationView.as_view(), name='credential-registration-complete'),
    path('authentication/begin/', MemberBeginAuthenticationView.as_view(), name='credential-authentication-begin'),
    path(
        'authentication/complete/',
        MemberCompleteAuthenticationView.as_view(),
        name='credential-authentication-complete',
    ),
    path('jsi18n/', JavaScriptCatalog.as_view(packages=['django_otp_webauthn']), name='js-i18n-catalog'),
]
