import json
import logging
import time

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import Http404
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django_otp_webauthn import exceptions
from django_otp_webauthn.models import WebAuthnCredential
from django_otp_webauthn.views import (
    BeginCredentialAuthenticationView,
    BeginCredentialRegistrationView,
    CompleteCredentialAuthenticationView,
    CompleteCredentialRegistrationView,
)

from core.utils import enqueue_task_on_commit, send_email_task

logger = logging.getLogger('date')

RECENT_AUTH_SESSION_KEY = 'members_recent_auth_at'


def get_rp_name(request):
    return settings.CONTENT_VARIABLES.get('ASSOCIATION_NAME', '')


def mark_recent_auth(request):
    request.session[RECENT_AUTH_SESSION_KEY] = int(time.time())


def has_recent_auth(request):
    authenticated_at = request.session.get(RECENT_AUTH_SESSION_KEY)
    if not isinstance(authenticated_at, int):
        return False
    return time.time() - authenticated_at <= settings.PASSKEY_REGISTRATION_MAX_AUTH_AGE


@receiver(user_logged_in, dispatch_uid='members.webauthn.mark_recent_auth')
def _mark_recent_auth_on_login(sender, request, user, **kwargs):
    if request is not None and hasattr(request, 'session'):
        mark_recent_auth(request)


def notify_passkey_change(user, credential_name, added):
    if not user.email:
        return
    template = 'members/passkey_added_email.txt' if added else 'members/passkey_removed_email.txt'
    subject = _('A passkey was added to your account') if added else _('A passkey was removed from your account')
    body = render_to_string(
        template,
        {
            'user': user,
            'credential_name': credential_name,
            'association_name': get_rp_name(None),
        },
    )
    enqueue_task_on_commit(send_email_task, subject, body, None, [user.email])


class RecentAuthRequired(exceptions.OTPWebAuthnApiError):
    status_code = 403
    default_code = 'recent_auth_required'
    default_detail = 'Sign in again before adding a passkey.'


class PasskeysEnabledMixin:
    def initial(self, request, *args, **kwargs):
        if not settings.PASSKEYS_ENABLED:
            raise Http404
        super().initial(request, *args, **kwargs)


class MemberRegistrationMixin(PasskeysEnabledMixin):
    def user_is_mfa_enrolled(self, user):
        from .two_factor import member_has_2fa

        return member_has_2fa(user)

    def check_can_register(self):
        if not has_recent_auth(self.request):
            raise RecentAuthRequired(detail=_('Sign in again before adding a passkey.'))


class MemberBeginRegistrationView(MemberRegistrationMixin, BeginCredentialRegistrationView):
    pass


class MemberCompleteRegistrationView(MemberRegistrationMixin, CompleteCredentialRegistrationView):
    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        if response.status_code == 200:
            credential = WebAuthnCredential.objects.get(pk=json.loads(response.content)['id'], user=self.request.user)
            logger.info('Passkey registered for member %s (credential %s)', self.request.user.pk, credential.pk)
            notify_passkey_change(self.request.user, credential.name, added=True)
        return response


class MemberBeginAuthenticationView(PasskeysEnabledMixin, BeginCredentialAuthenticationView):
    pass


class MemberCompleteAuthenticationView(PasskeysEnabledMixin, CompleteCredentialAuthenticationView):
    def complete_auth(self, device):
        was_authenticated = self.request.user.is_authenticated
        super().complete_auth(device)
        if was_authenticated:
            # auth_login() rotates the key for fresh logins; do the same when an
            # existing session is upgraded to verified.
            self.request.session.cycle_key()
        mark_recent_auth(self.request)
        logger.info('Passkey sign-in for member %s (credential %s)', device.user_id, device.pk)

    def get_redirect_url(self):
        from .two_factor import INFERRED_REDIRECT_SESSION_KEY

        redirect_to = super().get_redirect_url()
        if redirect_to:
            return redirect_to
        # Fall back to the referer-inferred target stored by MemberLoginView.
        inferred = self.request.session.pop(INFERRED_REDIRECT_SESSION_KEY, '')
        if url_has_allowed_host_and_scheme(
            inferred,
            allowed_hosts=self.get_success_url_allowed_hosts(),
            require_https=self.request.is_secure(),
        ):
            return inferred
        return ''

    def get_success_url(self):
        return self.get_redirect_url() or resolve_url('index')

    def handle_exception(self, exc):
        if isinstance(exc, exceptions.OTPWebAuthnApiError):
            logger.warning('Passkey sign-in failed: %s', getattr(exc, 'code', exc.__class__.__name__))
        return super().handle_exception(exc)
