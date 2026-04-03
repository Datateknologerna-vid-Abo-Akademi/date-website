import logging

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView
import django_otp
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm, TOTPDeviceForm
from two_factor.views import BackupTokensView, DisableView, LoginView, QRGeneratorView, SetupView

logger = logging.getLogger('date')


def member_has_2fa(user):
    return user.is_authenticated and TOTPDevice.objects.filter(user=user, confirmed=True).exists()


class UsernameOrEmailAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Username or email')
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['password'].widget.attrs.setdefault('autocomplete', 'current-password')


class StrictTOTPDeviceForm(TOTPDeviceForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tolerance = 1


class MemberLoginView(LoginView):
    template_name = 'two_factor/core/login.html'
    form_list = (
        (LoginView.AUTH_STEP, UsernameOrEmailAuthenticationForm),
        (LoginView.TOKEN_STEP, AuthenticationTokenForm),
        (LoginView.BACKUP_STEP, BackupTokenForm),
    )


class MemberSetupView(SetupView):
    template_name = 'two_factor/core/setup.html'
    success_url = 'members:info'

    def done(self, form_list, **kwargs):
        try:
            del self.request.session[self.session_key_name]
        except KeyError:
            logger.warning('2FA setup session key missing on done(); session may have expired')

        method = self.get_method()
        if method.code == 'generator':
            form = [form for form in form_list if isinstance(form, TOTPDeviceForm)][0]
            device = form.save()
        else:
            device = self.get_device()
            device.confirmed = True
            device.save()

        django_otp.login(self.request, device)
        return redirect(self.get_success_url())


class MemberDisableView(DisableView):
    template_name = 'two_factor/profile/disable.html'
    success_url = reverse_lazy('members:info')


class MemberBackupTokensView(BackupTokensView):
    template_name = 'two_factor/core/backup_tokens.html'


class MemberQRGeneratorView(QRGeneratorView):
    pass


class TwoFactorProfileRedirectView(RedirectView):
    pattern_name = 'members:info'
