import logging
from urllib.parse import urlsplit, urlunsplit

from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
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
INFERRED_REDIRECT_SESSION_KEY = 'members_login_inferred_next'


def member_has_2fa(user):
    return user.is_authenticated and TOTPDevice.objects.filter(user=user, confirmed=True).exists()


class UsernameOrEmailAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Username or email')
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['password'].widget.attrs.setdefault('autocomplete', 'current-password')


class StrictTOTPDeviceForm(TOTPDeviceForm):
    def __init__(self, key, user, *args, **kwargs):
        super().__init__(key, user, *args, **kwargs)
        self.tolerance = 1


class MemberLoginView(LoginView):
    template_name = 'members/registration/login.html'
    form_list = (
        (LoginView.AUTH_STEP, UsernameOrEmailAuthenticationForm),
        (LoginView.TOKEN_STEP, AuthenticationTokenForm),
        (LoginView.BACKUP_STEP, BackupTokenForm),
    )

    def get(self, request, *args, **kwargs):
        if self.redirect_field_name not in request.GET:
            request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
            redirect_to = self._get_referer_redirect_target(request)
            if redirect_to:
                request.session[INFERRED_REDIRECT_SESSION_KEY] = redirect_to

        return super().get(request, *args, **kwargs)

    def get_redirect_url(self):
        redirect_to = super().get_redirect_url()
        if redirect_to:
            return redirect_to

        redirect_to = self.request.session.get(INFERRED_REDIRECT_SESSION_KEY, '')
        if url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts=self.get_success_url_allowed_hosts(),
            require_https=self.request.is_secure(),
        ):
            return redirect_to
        return ''

    def get_success_url(self):
        return self.get_redirect_url() or resolve_url('index')

    def _get_referer_redirect_target(self, request):
        referer = request.META.get('HTTP_REFERER')
        if not referer:
            return None

        if not url_has_allowed_host_and_scheme(
            referer,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return None

        referer_parts = urlsplit(referer)
        if referer_parts.path == request.path:
            return None

        return urlunsplit(('', '', referer_parts.path or '/', referer_parts.query, ''))

    def done(self, form_list, **kwargs):
        response = super().done(form_list, **kwargs)
        redirect_to = self.get_success_url()
        target = self.get_redirect_url()

        if getattr(self.get_user(), 'otp_device', None) or not target or not OTPRequiredMixin.is_otp_view(target):
            self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
            return response

        resolver_match = resolve(target)
        if resolver_match.namespace == 'admin' and self.request.user.is_active and self.request.user.is_staff and not member_has_2fa(self.request.user):
            self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
            return HttpResponseRedirect(redirect_to)

        if target:
            self.request.session['next'] = redirect_to
        self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
        return redirect('two_factor:setup')


class MemberSetupView(SetupView):
    template_name = 'two_factor/core/setup.html'

    def get_form_list(self):
        form_list = super().get_form_list()
        if form_list.get('generator') is TOTPDeviceForm:
            form_list['generator'] = StrictTOTPDeviceForm
        return form_list

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
        next_target = request.session.pop('next', None)
        # The value comes from get_success_url() during login, but validate it
        # before redirecting in case the session is tampered with.
        if next_target and url_has_allowed_host_and_scheme(
            next_target,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_target)
        return redirect('index')


class TwoFactorProfileRedirectView(RedirectView):
    pattern_name = 'members:info'
