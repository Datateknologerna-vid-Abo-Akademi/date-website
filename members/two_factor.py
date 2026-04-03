import logging

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import resolve, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView
import django_otp
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm, TOTPDeviceForm
from two_factor.views import (
    BackupTokensView,
    DisableView,
    LoginView,
    QRGeneratorView,
    SetupCompleteView,
    SetupView,
)
from two_factor.views.mixins import OTPRequiredMixin

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

    def done(self, form_list, **kwargs):
        response = super().done(form_list, **kwargs)
        redirect_to = self.get_success_url()
        target = self.request.GET.get(self.redirect_field_name)

        if getattr(self.get_user(), 'otp_device', None) or not target or not OTPRequiredMixin.is_otp_view(target):
            return response

        resolver_match = resolve(target)
        admin_site = getattr(resolver_match.func, 'admin_site', None)
        if admin_site and self.request.user.is_active and self.request.user.is_staff and not member_has_2fa(self.request.user):
            return HttpResponseRedirect(redirect_to)

        if target:
            self.request.session['next'] = redirect_to
        return redirect('two_factor:setup')


class MemberSetupView(SetupView):
    template_name = 'two_factor/core/setup.html'

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


class MemberSetupCompleteView(SetupCompleteView):
    def get(self, request, *args, **kwargs):
        if request.session.get('next'):
            return redirect(request.session.get('next'))
        return redirect('members:info')


class TwoFactorProfileRedirectView(RedirectView):
    pattern_name = 'members:info'
