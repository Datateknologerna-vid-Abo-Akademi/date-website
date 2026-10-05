import logging
from urllib.parse import urlsplit, urlunsplit

import django_otp
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, resolve_url
from django.urls import resolve, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import RedirectView, TemplateView
from django_otp import devices_for_user
from django_otp.decorators import otp_required
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp_webauthn.models import WebAuthnCredential
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
    """True when the member has a confirmed second factor (TOTP or passkey); backup codes alone don't count."""
    if not user.is_authenticated:
        return False
    return any(not isinstance(device, StaticDevice) for device in devices_for_user(user, confirmed=True))


def member_has_totp(user):
    return user.is_authenticated and TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def member_has_passkey(user):
    return user.is_authenticated and WebAuthnCredential.objects.filter(user=user, confirmed=True).exists()


def two_factor_context(user):
    return {
        'two_factor_enabled': member_has_2fa(user),
        'has_totp': member_has_totp(user),
        'has_passkey': member_has_passkey(user),
        'passkeys_enabled': settings.PASSKEYS_ENABLED,
    }


def should_redirect_to_two_factor_setup(user, target):
    if not target or not OTPRequiredMixin.is_otp_view(target):
        return False

    resolver_match = resolve(target)
    if resolver_match.namespace == 'admin' and user.is_active and user.is_staff and not member_has_2fa(user):
        return False

    return True


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

    def has_backup_step(self):
        # two_factor only knows TOTP-style default devices. A passkey-only member
        # signing in with a password must still verify (passkey or backup
        # token) instead of ending up logged in but unverified.
        user = self.get_user()
        return bool(
            user
            and member_has_2fa(user)
            and self.TOKEN_STEP not in self.storage.validated_step_data
            and not self.remember_agent
        )

    condition_dict = {
        **LoginView.condition_dict,
        LoginView.BACKUP_STEP: has_backup_step,
    }

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        context['passkeys_enabled'] = settings.PASSKEYS_ENABLED
        return context

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

        if not should_redirect_to_two_factor_setup(self.request.user, target):
            self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
            return HttpResponseRedirect(redirect_to)

        if target:
            self.request.session['next'] = redirect_to
        self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, None)
        return redirect('two_factor:setup')


class MemberSetupView(SetupView):
    template_name = 'two_factor/core/setup.html'

    def dispatch(self, request, *args, **kwargs):
        # two_factor only skips setup when a TOTP default device exists. Without
        # this, an unverified session of a passkey-only member could enrol its
        # own TOTP device and upgrade itself to verified.
        user = request.user
        if user.is_authenticated and member_has_2fa(user) and not user.is_verified():
            messages.error(request, _('Verify with your existing passkey or authenticator before adding another.'))
            return redirect_to_login(request.get_full_path(), resolve_url(settings.OTP_LOGIN_URL))
        return super().dispatch(request, *args, **kwargs)

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


class PasskeysEnabledViewMixin:
    def dispatch(self, request, *args, **kwargs):
        if not settings.PASSKEYS_ENABLED:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class PasskeyListView(PasskeysEnabledViewMixin, LoginRequiredMixin, TemplateView):
    template_name = 'two_factor/profile/passkeys.html'

    def get_context_data(self, **kwargs):
        from .webauthn import has_recent_auth

        user = self.request.user
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'credentials': WebAuthnCredential.objects.filter(user=user, confirmed=True).order_by('created_at'),
                'can_register': has_recent_auth(self.request) and (user.is_verified() or not member_has_2fa(user)),
                'has_backup_tokens': StaticDevice.objects.filter(user=user, token_set__isnull=False).exists(),
            }
        )
        return context


class PasskeyRenameForm(forms.Form):
    name = forms.CharField(max_length=WebAuthnCredential._meta.get_field('name').max_length)


@method_decorator([never_cache, otp_required], name='dispatch')
class PasskeyRenameView(PasskeysEnabledViewMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        credential = get_object_or_404(WebAuthnCredential, pk=pk, user=request.user)
        form = PasskeyRenameForm(request.POST)
        if form.is_valid():
            credential.name = form.cleaned_data['name']
            credential.save(update_fields=['name'])
        else:
            messages.error(request, _('Invalid passkey name.'))
        return redirect('two_factor:passkeys')


@method_decorator([never_cache, otp_required], name='dispatch')
class PasskeyDeleteView(PasskeysEnabledViewMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        from .webauthn import notify_passkey_change

        credential = get_object_or_404(WebAuthnCredential, pk=pk, user=request.user)
        name = credential.name
        credential.delete()
        if not member_has_2fa(request.user):
            # Backup codes alone are not a second factor; drop them so the
            # member isn't left half-enrolled and unable to re-enrol.
            StaticDevice.objects.filter(user=request.user).delete()
        logger.info('Passkey %s deleted by member %s', pk, request.user.pk)
        notify_passkey_change(request.user, name, added=False)
        messages.success(request, _('Passkey removed.'))
        return redirect('two_factor:passkeys')
