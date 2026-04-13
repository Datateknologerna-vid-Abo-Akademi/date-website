import logging
import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

logger = logging.getLogger('date')

GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL = 'https://api.github.com/user'


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
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    return redirect(f'{GITHUB_AUTHORIZE_URL}?{query}')


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

    return _handle_login(request, github_id, github_user.get('email'))


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

    request.user.github_id = github_id
    request.user.save(update_fields=['github_id'])
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

    login(request, member, backend='members.backends.AuthBackend')
    logger.info('GitHub login successful for member %s', member.username)

    next_url = request.session.pop('github_oauth_next', None) or settings.LOGIN_REDIRECT_URL
    return redirect(next_url)
