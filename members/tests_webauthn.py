import itertools
import json
import time
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp_webauthn.models import WebAuthnCredential

from members.backends import AuthBackend
from members.checks import check_passkey_settings
from members.models import ORDINARY_MEMBER, Member, MembershipType
from members.two_factor import INFERRED_REDIRECT_SESSION_KEY, member_has_2fa
from members.webauthn import RECENT_AUTH_SESSION_KEY

from .tests import GITHUB_SETTINGS, _mock_github_responses

_credential_ids = itertools.count()

AUTH_STATE = {'challenge': 'Y2hhbGxlbmdl', 'require_user_verification': True}
REGISTER_STATE = {'challenge': 'Y2hhbGxlbmdl'}


def make_passkey(user, confirmed=True, name='Laptop'):
    return WebAuthnCredential.objects.create(
        user=user,
        name=name,
        confirmed=confirmed,
        credential_id=f'credential-{next(_credential_ids)}'.encode(),
        public_key=b'public-key',
    )


class PasskeyTestMixin:
    password = 'secret12345'

    def setUp(self):
        self.client = Client()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = self.make_member('passkeyuser')

    def make_member(self, username, **extra):
        return Member.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password=self.password,
            membership_type=self.membership_type,
            first_name='Pass',
            last_name='Key',
            **extra,
        )

    def login(self, user, verified_device=None):
        self.client.force_login(user, backend='members.backends.AuthBackend')
        if verified_device is not None:
            session = self.client.session
            session[DEVICE_ID_SESSION_KEY] = verified_device.persistent_id
            session.save()

    def set_session(self, **values):
        session = self.client.session
        session.update(values)
        session.save()

    def post_json(self, url, data=None):
        return self.client.post(url, data=json.dumps(data or {}), content_type='application/json')


class PasskeySettingsCheckTests(TestCase):
    @override_settings(PASSKEYS_ENABLED=False, DEBUG=True)
    def test_disabled_in_debug_is_silent(self):
        self.assertEqual(check_passkey_settings(None), [])

    @override_settings(PASSKEYS_ENABLED=False, DEBUG=False)
    def test_disabled_in_production_warns(self):
        self.assertEqual([e.id for e in check_passkey_settings(None)], ['members.W001'])

    def _ids(self, rp_id, origins):
        with override_settings(PASSKEYS_ENABLED=True, OTP_WEBAUTHN_RP_ID=rp_id, OTP_WEBAUTHN_ALLOWED_ORIGINS=origins):
            return [e.id for e in check_passkey_settings(None)]

    def test_wildcard_origin_is_rejected(self):
        self.assertIn('members.E001', self._ids('example.com', ['https://*.example.com']))

    def test_plain_http_origin_is_rejected(self):
        self.assertIn('members.E002', self._ids('example.com', ['http://example.com']))

    def test_origin_outside_rp_id_is_rejected(self):
        self.assertIn('members.E003', self._ids('example.com', ['https://example.org']))

    def test_subdomain_origin_is_allowed(self):
        self.assertEqual(self._ids('example.com', ['https://example.com', 'https://www.example.com']), [])

    def test_http_localhost_is_allowed(self):
        self.assertEqual(self._ids('localhost', ['http://localhost:8000']), [])

    def test_missing_association_name_is_rejected(self):
        with override_settings(CONTENT_VARIABLES={}):
            self.assertIn('members.E004', self._ids('localhost', ['http://localhost:8000']))


class AuthBackendTests(PasskeyTestMixin, TestCase):
    def test_missing_credentials_return_none(self):
        backend = AuthBackend()
        self.assertIsNone(backend.authenticate(None, username=None, password=self.password))
        self.assertIsNone(backend.authenticate(None, username=self.member.username, password=None))

    def test_missing_username_with_null_emails_does_not_crash(self):
        self.make_member('another')
        Member.objects.update(email=None)
        self.assertIsNone(AuthBackend().authenticate(None, webauthn_credential=object()))

    def test_inactive_member_is_rejected(self):
        self.member.is_active = False
        self.member.save()
        self.assertIsNone(AuthBackend().authenticate(None, username=self.member.username, password=self.password))
        self.assertIsNone(AuthBackend().authenticate(None, username=self.member.email, password=self.password))


class MemberHas2faTests(PasskeyTestMixin, TestCase):
    def test_no_devices(self):
        self.assertFalse(member_has_2fa(self.member))

    def test_totp_only(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        self.assertTrue(member_has_2fa(self.member))

    def test_passkey_only(self):
        make_passkey(self.member)
        self.assertTrue(member_has_2fa(self.member))

    def test_totp_and_passkey(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        make_passkey(self.member)
        self.assertTrue(member_has_2fa(self.member))

    def test_unconfirmed_devices_do_not_count(self):
        TOTPDevice.objects.create(user=self.member, confirmed=False, name='default')
        make_passkey(self.member, confirmed=False)
        self.assertFalse(member_has_2fa(self.member))

    def test_backup_codes_alone_do_not_count(self):
        StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        self.assertFalse(member_has_2fa(self.member))


class PasskeyAdminTests(PasskeyTestMixin, TestCase):
    def make_superuser(self, username):
        return Member.objects.create_superuser(
            username=username,
            email=f'{username}@example.com',
            password=self.password,
            membership_type=self.membership_type,
        )

    def test_unverified_passkey_admin_is_denied(self):
        admin_user = self.make_superuser('passkeyadmin')
        make_passkey(admin_user)
        self.login(admin_user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.headers['Location'])

    def test_passkey_verified_admin_is_allowed(self):
        admin_user = self.make_superuser('passkeyadmin')
        credential = make_passkey(admin_user)
        self.login(admin_user, verified_device=credential)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

    def test_disable_action_removes_all_device_types(self):
        totp = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        static = StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        passkey = make_passkey(self.member)
        self.login(self.make_superuser('admintest'))

        self.client.post(
            reverse('admin:members_member_changelist'),
            {'action': 'disable_two_factor', '_selected_action': [self.member.pk]},
        )

        self.assertFalse(TOTPDevice.objects.filter(pk=totp.pk).exists())
        self.assertFalse(StaticDevice.objects.filter(pk=static.pk).exists())
        self.assertFalse(WebAuthnCredential.objects.filter(pk=passkey.pk).exists())

    def _staff_with_permissions(self, username, *codenames):
        staff = self.make_member(username)
        group, _ = Group.objects.get_or_create(name='styrelse')
        staff.groups.add(group)
        staff.user_permissions.add(
            *Permission.objects.filter(content_type__app_label='members', codename__in=codenames)
        )
        return Member.objects.get(pk=staff.pk)

    def test_disable_action_requires_change_permission(self):
        self.login(self._staff_with_permissions('viewonly', 'view_member'))
        response = self.client.get(reverse('admin:members_member_changelist'))
        self.assertEqual(response.status_code, 200)
        actions = [name for name, _ in response.context['action_form'].fields['action'].choices]
        self.assertNotIn('disable_two_factor', actions)

    def test_non_superuser_cannot_disable_superuser_2fa(self):
        target = self.make_superuser('targetadmin')
        totp = TOTPDevice.objects.create(user=target, confirmed=True, name='default')
        passkey = make_passkey(target)
        self.login(self._staff_with_permissions('editor', 'view_member', 'change_member'))

        self.client.post(
            reverse('admin:members_member_changelist'),
            {'action': 'disable_two_factor', '_selected_action': [target.pk]},
        )

        self.assertTrue(TOTPDevice.objects.filter(pk=totp.pk).exists())
        self.assertTrue(WebAuthnCredential.objects.filter(pk=passkey.pk).exists())


class PasskeyLoginWizardTests(PasskeyTestMixin, TestCase):
    def _post_auth_step(self):
        response = self.client.get(reverse('members:login'))
        prefix = response.context['wizard']['management_form'].prefix
        response = self.client.post(
            reverse('members:login'),
            data={
                f'{prefix}-current_step': 'auth',
                'auth-username': self.member.username,
                'auth-password': self.password,
            },
        )
        return prefix, response

    def test_passkey_only_password_login_requires_backup_step(self):
        make_passkey(self.member)
        _, response = self._post_auth_step()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['wizard']['steps'].current, 'backup')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'passkey-verification-placeholder')

    @override_settings(PASSKEYS_ENABLED=False)
    def test_passkeys_disabled_backup_step_fails_closed_with_recovery_hint(self):
        make_passkey(self.member)
        _, response = self._post_auth_step()

        self.assertEqual(response.context['wizard']['steps'].current, 'backup')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotContains(response, 'passkey-verification-placeholder')
        # Swedish is the site default language.
        self.assertContains(response, 'kontakta webbplatsens administratörer')

    def test_backup_token_completes_passkey_only_login(self):
        make_passkey(self.member)
        static = StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        static.token_set.create(token='abcd1234')
        prefix, _ = self._post_auth_step()

        response = self.client.post(
            reverse('members:login'),
            data={f'{prefix}-current_step': 'backup', 'backup-otp_token': 'abcd1234'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)
        self.assertEqual(self.client.session[DEVICE_ID_SESSION_KEY], static.persistent_id)

    def test_totp_member_still_gets_token_step(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        make_passkey(self.member)
        _, response = self._post_auth_step()
        self.assertEqual(response.context['wizard']['steps'].current, 'token')

    def test_member_without_2fa_logs_in_directly(self):
        _, response = self._post_auth_step()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)


@override_settings(**GITHUB_SETTINGS)
class PasskeyGitHubLoginTests(PasskeyTestMixin, TestCase):
    def test_passkey_only_member_lands_on_backup_step(self):
        member = self.make_member('ghpasskey', github_id=4242)
        make_passkey(member)
        self.set_session(github_oauth_state='valid-state', github_oauth_intent='login')

        mock_post, mock_get = _mock_github_responses(github_id=4242, email=member.email)
        with mock_post, mock_get:
            response = self.client.get(reverse('members:github_callback'), {'state': 'valid-state', 'code': 'c'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].startswith(reverse('members:login')))
        self.assertNotIn('_auth_user_id', self.client.session)

        wizard_session = self.client.session['wizard_member_login_view']
        self.assertEqual(wizard_session['step'], 'backup')
        self.assertEqual(wizard_session['user_pk'], str(member.pk))


class PasskeyManagementTests(PasskeyTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.passkey = make_passkey(self.member, name='Mine')
        self.other = self.make_member('otherpasskey')
        self.other_passkey = make_passkey(self.other, name='Theirs')

    @override_settings(PASSKEYS_ENABLED=False)
    def test_page_is_404_when_disabled(self):
        self.login(self.member, verified_device=self.passkey)
        self.assertEqual(self.client.get(reverse('two_factor:passkeys')).status_code, 404)

    def test_page_requires_login(self):
        response = self.client.get(reverse('two_factor:passkeys'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('members:login'), response.headers['Location'])

    def test_lists_only_own_credentials(self):
        self.login(self.member, verified_device=self.passkey)
        response = self.client.get(reverse('two_factor:passkeys'))
        self.assertEqual(list(response.context['credentials']), [self.passkey])
        self.assertContains(response, 'Mine')
        self.assertNotContains(response, 'Theirs')

    def test_cannot_rename_or_delete_another_members_passkey(self):
        self.login(self.member, verified_device=self.passkey)
        rename = self.client.post(reverse('two_factor:passkey_rename', args=[self.other_passkey.pk]), {'name': 'x'})
        delete = self.client.post(reverse('two_factor:passkey_delete', args=[self.other_passkey.pk]))
        self.assertEqual(rename.status_code, 404)
        self.assertEqual(delete.status_code, 404)
        self.other_passkey.refresh_from_db()
        self.assertEqual(self.other_passkey.name, 'Theirs')

    def test_rename_and_delete_require_verified_session(self):
        self.login(self.member)
        for name in ('two_factor:passkey_rename', 'two_factor:passkey_delete'):
            response = self.client.post(reverse(name, args=[self.passkey.pk]), {'name': 'x'})
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('members:login'), response.headers['Location'])
        self.passkey.refresh_from_db()
        self.assertEqual(self.passkey.name, 'Mine')

    def test_rename_and_delete_reject_get(self):
        self.login(self.member, verified_device=self.passkey)
        for name in ('two_factor:passkey_rename', 'two_factor:passkey_delete'):
            self.assertEqual(self.client.get(reverse(name, args=[self.passkey.pk])).status_code, 405)

    def test_rename(self):
        self.login(self.member, verified_device=self.passkey)
        self.client.post(reverse('two_factor:passkey_rename', args=[self.passkey.pk]), {'name': 'Phone'})
        self.passkey.refresh_from_db()
        self.assertEqual(self.passkey.name, 'Phone')

    @patch('members.webauthn.enqueue_task_on_commit')
    def test_deleting_last_passkey_removes_backup_codes_and_notifies(self, mock_enqueue):
        StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        self.login(self.member, verified_device=self.passkey)

        self.client.post(reverse('two_factor:passkey_delete', args=[self.passkey.pk]))

        self.assertFalse(WebAuthnCredential.objects.filter(pk=self.passkey.pk).exists())
        self.assertFalse(StaticDevice.objects.filter(user=self.member).exists())
        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.args[4], [self.member.email])

    @patch('members.webauthn.enqueue_task_on_commit')
    def test_deleting_one_of_several_factors_keeps_backup_codes(self, mock_enqueue):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        self.login(self.member, verified_device=self.passkey)

        self.client.post(reverse('two_factor:passkey_delete', args=[self.passkey.pk]))

        self.assertTrue(StaticDevice.objects.filter(user=self.member).exists())


class PasskeyRegistrationApiTests(PasskeyTestMixin, TestCase):
    begin_url = reverse('otp_webauthn:credential-registration-begin')
    complete_url = reverse('otp_webauthn:credential-registration-complete')

    def test_begin_requires_recent_authentication(self):
        self.login(self.member)
        self.set_session(**{RECENT_AUTH_SESSION_KEY: int(time.time()) - 3600})
        response = self.post_json(self.begin_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'recent_auth_required')

    def test_begin_allowed_after_fresh_login_without_2fa(self):
        self.login(self.member)
        response = self.post_json(self.begin_url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('challenge', response.json())

    def test_begin_rejected_for_enrolled_unverified_member(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        self.login(self.member)
        response = self.post_json(self.begin_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(response.json()['code'], 'recent_auth_required')

    def test_begin_allowed_for_backup_codes_only_member(self):
        StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        self.login(self.member)
        self.assertEqual(self.post_json(self.begin_url).status_code, 200)

    def test_begin_requires_login(self):
        self.assertNotEqual(self.post_json(self.begin_url).status_code, 200)

    @patch('members.webauthn.enqueue_task_on_commit')
    def test_complete_notifies_member(self, mock_enqueue):
        self.login(self.member)
        self.set_session(otp_webauthn_register_state=REGISTER_STATE)
        created = []

        def register_complete(helper, user, state, data):
            created.append(make_passkey(user, name='New key'))
            return created[0]

        with patch('django_otp_webauthn.helpers.WebAuthnHelper.register_complete', register_complete):
            response = self.post_json(self.complete_url, {'id': 'x'})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.client.session[DEVICE_ID_SESSION_KEY], created[0].persistent_id)
        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.args[4], [self.member.email])

    @patch('members.webauthn.enqueue_task_on_commit')
    def test_complete_rotates_session_key_when_upgrading_to_verified(self, _mock_enqueue):
        self.login(self.member)
        self.set_session(otp_webauthn_register_state=REGISTER_STATE)
        old_key = self.client.session.session_key

        def register_complete(helper, user, state, data):
            return make_passkey(user)

        with patch('django_otp_webauthn.helpers.WebAuthnHelper.register_complete', register_complete):
            response = self.post_json(self.complete_url, {'id': 'x'})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(self.client.session.session_key, old_key)


class PasskeySecurityRegressionTests(PasskeyTestMixin, TestCase):
    def test_unverified_passkey_member_cannot_enrol_totp(self):
        make_passkey(self.member)
        self.login(self.member)
        response = self.client.get(reverse('two_factor:setup'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('members:login')))

    def test_verified_passkey_member_can_enrol_totp(self):
        passkey = make_passkey(self.member)
        self.login(self.member, verified_device=passkey)
        self.assertEqual(self.client.get(reverse('two_factor:setup')).status_code, 200)

    @override_settings(**GITHUB_SETTINGS)
    def test_github_connect_requires_recent_authentication(self):
        self.login(self.member)
        self.set_session(**{RECENT_AUTH_SESSION_KEY: int(time.time()) - 3600})
        response = self.client.post(reverse('members:github_connect'))
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)

    @override_settings(**GITHUB_SETTINGS)
    def test_github_connect_allowed_after_fresh_login(self):
        self.login(self.member)
        response = self.client.post(reverse('members:github_connect'))
        self.assertTrue(response.url.startswith('https://github.com/login/oauth/authorize'))

    @patch('members.webauthn.enqueue_task_on_commit')
    def test_notification_email_is_not_html_escaped(self, mock_enqueue):
        from members.webauthn import notify_passkey_change

        notify_passkey_change(self.member, 'Tom & "Jerry"', added=True)
        self.assertIn('Tom & "Jerry"', mock_enqueue.call_args.args[2])


class PasskeyAuthenticationApiTests(PasskeyTestMixin, TestCase):
    complete_url = reverse('otp_webauthn:credential-authentication-complete')

    def setUp(self):
        super().setUp()
        self.passkey = make_passkey(self.member)

    def _complete(self, query=''):
        self.set_session(otp_webauthn_authentication_state=AUTH_STATE)
        with patch('django_otp_webauthn.helpers.WebAuthnHelper.authenticate_complete', return_value=self.passkey):
            return self.post_json(self.complete_url + query, {'id': 'x'})

    def test_anonymous_passkey_sign_in_logs_in_verified(self):
        response = self._complete()
        self.assertEqual(response.status_code, 200, response.content)
        session = self.client.session
        self.assertEqual(int(session['_auth_user_id']), self.member.pk)
        self.assertEqual(session[DEVICE_ID_SESSION_KEY], self.passkey.persistent_id)
        self.assertIn(RECENT_AUTH_SESSION_KEY, session)
        self.assertEqual(response.json()['redirect_url'], reverse('index'))

    def test_existing_session_is_rotated_and_verified(self):
        self.login(self.member)
        before = self.client.session.session_key
        response = self._complete()
        self.assertEqual(response.status_code, 200, response.content)
        session = self.client.session
        self.assertNotEqual(session.session_key, before)
        self.assertEqual(session[DEVICE_ID_SESSION_KEY], self.passkey.persistent_id)
        self.assertEqual(int(session['_auth_user_id']), self.member.pk)

    def test_inactive_member_is_rejected(self):
        self.member.is_active = False
        self.member.save()
        response = self._complete()
        self.assertGreaterEqual(response.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_safe_next_is_used(self):
        response = self._complete('?next=/events/')
        self.assertEqual(response.json()['redirect_url'], '/events/')

    def test_session_inferred_next_is_used_as_fallback(self):
        self.set_session(**{INFERRED_REDIRECT_SESSION_KEY: '/polls/'})
        response = self._complete()
        self.assertEqual(response.json()['redirect_url'], '/polls/')

    def test_external_next_is_ignored(self):
        self.set_session(**{INFERRED_REDIRECT_SESSION_KEY: 'https://evil.example/'})
        response = self._complete('?next=https://evil.example/phish')
        self.assertEqual(response.json()['redirect_url'], reverse('index'))

    def test_state_is_single_use(self):
        self._complete()
        with patch('django_otp_webauthn.helpers.WebAuthnHelper.authenticate_complete', return_value=self.passkey):
            response = self.post_json(self.complete_url, {'id': 'x'})
        self.assertGreaterEqual(response.status_code, 400)


@override_settings(PASSKEYS_ENABLED=False)
class PasskeyEndpointsDisabledTests(PasskeyTestMixin, TestCase):
    def test_all_endpoints_404(self):
        self.login(self.member)
        for name in (
            'otp_webauthn:credential-registration-begin',
            'otp_webauthn:credential-registration-complete',
            'otp_webauthn:credential-authentication-begin',
            'otp_webauthn:credential-authentication-complete',
        ):
            self.assertEqual(self.post_json(reverse(name)).status_code, 404, name)

    def test_login_page_hides_passkey_button(self):
        response = self.client.get(reverse('members:login'))
        self.assertNotContains(response, 'passkey-verification-placeholder')


class BackupTokensDownloadTests(PasskeyTestMixin, TestCase):
    url = reverse('two_factor:backup_tokens_download')

    def _static_device(self, user, *tokens):
        device = StaticDevice.objects.create(user=user, confirmed=True, name='backup')
        for token in tokens:
            device.token_set.create(token=token)
        return device

    def test_unverified_session_is_redirected(self):
        self._static_device(self.member, 'aaaa1111')
        make_passkey(self.member)
        self.login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('aaaa1111', response.content.decode())

    def test_verified_member_downloads_only_their_codes(self):
        device = self._static_device(self.member, 'aaaa1111', 'bbbb2222')
        self._static_device(self.make_member('other'), 'zzzz9999')
        self.login(self.member, verified_device=device)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="date-backup-codes.txt"')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])
        body = response.content.decode()
        lines = body.splitlines()
        self.assertEqual(lines[-2:], ['aaaa1111', 'bbbb2222'])
        self.assertIn(self.member.username, lines[0])
        self.assertNotIn('zzzz9999', body)

    def test_no_codes_redirects_to_backup_page(self):
        passkey = make_passkey(self.member)
        self.login(self.member, verified_device=passkey)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('two_factor:backup_tokens'), fetch_redirect_response=False)

    def test_post_is_not_allowed(self):
        device = self._static_device(self.member, 'aaaa1111')
        self.login(self.member, verified_device=device)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_backup_page_links_to_download(self):
        device = self._static_device(self.member, 'aaaa1111')
        self.login(self.member, verified_device=device)
        response = self.client.get(reverse('two_factor:backup_tokens'))
        self.assertContains(response, self.url)
