import logging
import secrets
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from two_factor.views.utils import LoginStorage

from .two_factor import MemberLoginView, member_has_2fa, should_redirect_to_two_factor_setup

logger = logging.getLogger('date')

GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL = 'https://api.github.com/user'
GITHUB_EMAILS_URL = 'https://api.github.com/user/emails'
GITHUB_MFA_POLICY_ENROLLED = 'enrolled'
GITHUB_MFA_POLICY_STAFF = 'staff'
GITHUB_MFA_POLICY_OFF = 'off'


def _build_login_redirect(next_url=None):
    login_url = reverse('members:login')
    if next_url:
        return f'{login_url}?{urlencode({"next": next_url})}'
    return login_url


def _begin_two_factor_login(request, member, next_url):
    member.backend = 'members.backends.AuthBackend'
    storage = LoginStorage(MemberLoginView().get_prefix(request), request)
    storage.reset()
    storage.authenticated_user = member
    storage.data['authentication_time'] = int(time.time())
    storage.current_step = MemberLoginView.TOKEN_STEP
    return redirect(_build_login_redirect(next_url))


def _should_require_local_2fa(member):
    if not member_has_2fa(member):
        return False

    policy = str(getattr(settings, 'GITHUB_MFA_POLICY', GITHUB_MFA_POLICY_ENROLLED) or '').strip().lower()
    if policy == GITHUB_MFA_POLICY_OFF:
        return False
    if policy == GITHUB_MFA_POLICY_STAFF:
        return member.is_staff
    return True


def _github_redirect(request, intent):
    """Start the GitHub OAuth flow. intent is 'login' or 'connect'."""
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', None)
    if not client_id:
        messages.error(request, _('GitHub-inloggning är inte konfigurerad.'))
        return redirect(settings.LOGIN_URL)

    state = secrets.token_urlsafe(16)
    request.session['github_oauth_state'] = state
    request.session['github_oauth_intent'] = intent
    next_url = request.GET.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        request.session['github_oauth_next'] = next_url

    params = {
        'client_id': client_id,
        'scope': 'read:user user:email',
        'state': state,
    }
    return redirect(f'{GITHUB_AUTHORIZE_URL}?{urlencode(params)}')


def github_login(request):
    return _github_redirect(request, intent='login')


@login_required
def github_connect(request):
    if request.method != 'POST':
        return redirect('members:info')
    return _github_redirect(request, intent='connect')


@login_required
def github_disconnect(request):
    if request.method != 'POST':
        return redirect('members:info')
    member = request.user
    if member.github_id is None:
        messages.error(request, _('Inget GitHub-konto är kopplat.'))
    else:
        member.github_id = None
        member.save(update_fields=['github_id'])
        messages.success(request, _('GitHub-kontot har kopplats bort.'))
    return redirect('members:info')


def github_callback(request):
    from .models import Member

    error = request.GET.get('error')
    if error:
        logger.warning('GitHub OAuth error: %s', error)
        messages.error(request, _('GitHub-inloggningen misslyckades.'))
        return redirect(settings.LOGIN_URL)

    state = request.GET.get('state')
    expected_state = request.session.pop('github_oauth_state', None)
    intent = request.session.pop('github_oauth_intent', 'login')

    if not state or state != expected_state:
        logger.warning('GitHub OAuth state mismatch')
        messages.error(request, _('Ogiltig OAuth-begäran. Försök igen.'))
        return redirect(settings.LOGIN_URL)

    code = request.GET.get('code')
    if not code:
        messages.error(request, _('GitHub returnerade ingen auktoriseringskod.'))
        return redirect(settings.LOGIN_URL)

    # Exchange code for access token
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', None)
    client_secret = getattr(settings, 'GITHUB_CLIENT_SECRET', None)
    if not client_id or not client_secret:
        messages.error(request, _('GitHub-inloggning är inte konfigurerad.'))
        return redirect(settings.LOGIN_URL)

    try:
        token_response = requests.post(
            GITHUB_TOKEN_URL,
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
            },
            headers={'Accept': 'application/json'},
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except requests.RequestException as exc:
        logger.error('GitHub token exchange failed: %s', exc)
        messages.error(request, _('Kunde inte kommunicera med GitHub. Försök igen.'))
        return redirect(settings.LOGIN_URL)

    access_token = token_data.get('access_token')
    if not access_token:
        logger.warning('GitHub token response missing access_token: %s', token_data)
        messages.error(request, _('GitHub-inloggningen misslyckades.'))
        return redirect(settings.LOGIN_URL)

    # Fetch GitHub user profile
    try:
        user_response = requests.get(
            GITHUB_USER_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/vnd.github+json',
            },
            timeout=10,
        )
        user_response.raise_for_status()
        github_user = user_response.json()
    except requests.RequestException as exc:
        logger.error('GitHub user fetch failed: %s', exc)
        messages.error(request, _('Kunde inte hämta GitHub-profil. Försök igen.'))
        return redirect(settings.LOGIN_URL)

    github_id = github_user.get('id')
    if not github_id:
        messages.error(request, _('Kunde inte hämta GitHub-användar-ID.'))
        return redirect(settings.LOGIN_URL)

    if intent == 'connect':
        return _handle_connect(request, github_id)

    # Fetch verified primary email for account matching (user.email is often null)
    github_email = None
    try:
        emails_response = requests.get(
            GITHUB_EMAILS_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/vnd.github+json',
            },
            timeout=10,
        )
        emails_response.raise_for_status()
        for entry in emails_response.json():
            if entry.get('verified') and entry.get('primary'):
                github_email = entry.get('email')
                break
    except requests.RequestException as exc:
        logger.warning('GitHub emails fetch failed: %s', exc)

    return _handle_login(request, github_id, github_email)


def _handle_connect(request, github_id):
    from .models import Member

    if not request.user.is_authenticated:
        messages.error(request, _('Du måste vara inloggad för att koppla ett GitHub-konto.'))
        return redirect(settings.LOGIN_URL)

    # Check if this GitHub account is already linked to another member
    try:
        existing = Member.objects.get(github_id=github_id)
        if existing.pk != request.user.pk:
            messages.error(request, _('Det GitHub-kontot är redan kopplat till ett annat konto.'))
            return redirect('members:info')
        # Already linked to this member — nothing to do
        messages.info(request, _('GitHub-kontot är redan kopplat till ditt konto.'))
        return redirect('members:info')
    except Member.DoesNotExist:
        pass

    try:
        with transaction.atomic():
            request.user.github_id = github_id
            request.user.save(update_fields=['github_id'])
    except IntegrityError:
        messages.error(request, _('Det GitHub-kontot är redan kopplat till ett annat konto.'))
        return redirect('members:info')
    messages.success(request, _('GitHub-kontot har kopplats till ditt konto.'))
    return redirect('members:info')


def _handle_login(request, github_id, github_email):
    from .models import Member

    member = None
    try:
        member = Member.objects.get(github_id=github_id)
    except Member.DoesNotExist:
        if github_email:
            try:
                member = Member.objects.get(email=github_email)
                # Link this GitHub account for future logins
                member.github_id = github_id
                member.save(update_fields=['github_id'])
            except Member.DoesNotExist:
                pass

    if member is None:
        logger.info('GitHub login: no member found for github_id=%s email=%s', github_id, github_email)
        messages.error(
            request,
            _('Inget konto hittades för ditt GitHub-konto. Kontakta administratören.'),
        )
        return redirect(settings.LOGIN_URL)

    if not member.is_active:
        messages.error(request, _('Ditt konto är inaktiverat.'))
        return redirect(settings.LOGIN_URL)

    next_url = request.session.pop('github_oauth_next', None) or resolve_url(settings.LOGIN_REDIRECT_URL)
    if _should_require_local_2fa(member):
        logger.info('GitHub login requires local 2FA for member %s', member.username)
        return _begin_two_factor_login(request, member, next_url)

    login(request, member, backend='members.backends.AuthBackend')
    logger.info('GitHub login successful for member %s', member.username)

    if should_redirect_to_two_factor_setup(request.user, next_url):
        request.session['next'] = next_url
        return redirect('two_factor:setup')

    return redirect(next_url)
