import time
from inspect import signature
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import TOTP
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.forms import TOTPDeviceForm

from members.forms import (FunctionaryForm, MemberCreationForm, SignUpForm,
                           SubscriptionPaymentForm)
from members.functionary import get_selected_role, get_selected_year
from members.models import (Functionary, FunctionaryRole, Member,
                            MembershipType, ORDINARY_MEMBER, Subscription)
from members.two_factor import (
    INFERRED_REDIRECT_SESSION_KEY,
    MemberSetupView,
    StrictTOTPDeviceForm,
)


class UsernameValidatorTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)

    def test_member_creation_form_accepts_valid_username(self):
        form = MemberCreationForm(data={
            'username': 'valid_user123',
            'email': 'valid@example.com',
            'first_name': 'Valid',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertTrue(form.is_valid())

    def test_member_creation_form_rejects_invalid_username(self):
        form = MemberCreationForm(data={
            'username': 'invalid user',
            'email': 'user@example.com',
            'first_name': 'Invalid',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_member_creation_form_accepts_dotted_username(self):
        form = MemberCreationForm(data={
            'username': 'first.last',
            'email': 'dotted@example.com',
            'first_name': 'Dot',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertTrue(form.is_valid())

    def test_signup_form_rejects_invalid_username(self):
        form = SignUpForm(data={
            'username': 'bad!name',
            'email': 'user@example.com',
            'first_name': 'Bad',
            'last_name': 'Name',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)


class MemberCreationFormSaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)

    def test_save_hashes_password(self):
        form = MemberCreationForm(data={
            'username': 'hash_user',
            'email': 'hash@example.com',
            'first_name': 'Hash',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertTrue(form.is_valid())
        member = form.save()
        self.assertNotEqual(member.password, 'secret123')
        self.assertTrue(member.check_password('secret123'))


class SubscriptionPaymentFormTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='subscriber',
            password='pwd',
            membership_type=self.membership_type,
        )

    def _create_subscription(self, scale):
        return Subscription.objects.create(
            name=f"{scale}-sub",
            does_expire=True,
            renewal_scale=scale,
            renewal_period=1,
            price=100,
        )

    def test_expiry_dates_for_day_month_year(self):
        base_date = timezone.now().date()
        cases = [
            ('day', relativedelta(days=1)),
            ('month', relativedelta(months=1)),
            ('year', relativedelta(years=1)),
        ]
        for scale, delta in cases:
            with self.subTest(scale=scale):
                subscription = self._create_subscription(scale)
                form = SubscriptionPaymentForm(data={
                    'member': self.member.id,
                    'subscription': subscription.id,
                    'date_paid': base_date,
                    'amount_paid': '100.00',
                })
                self.assertTrue(form.is_valid())
                payment = form.save()
                self.assertEqual(payment.date_expires, base_date + delta)

    def test_non_expiring_subscription_keeps_null_expiry(self):
        subscription = Subscription.objects.create(
            name="lifetime",
            does_expire=False,
            renewal_scale=None,
            renewal_period=None,
            price=0,
        )
        form = SubscriptionPaymentForm(data={
            'member': self.member.id,
            'subscription': subscription.id,
            'date_paid': timezone.now().date(),
            'amount_paid': '0',
        })
        self.assertTrue(form.is_valid())
        payment = form.save()
        self.assertIsNone(payment.date_expires)


class FunctionaryFormTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='functionary',
            password='pwd',
            membership_type=self.membership_type,
        )
        self.role = FunctionaryRole.objects.create(title='Chair', board=True)

    def test_prevents_duplicate_year_role(self):
        Functionary.objects.create(member=self.member, functionary_role=self.role, year=2024)
        form = FunctionaryForm(data={
            'functionary_role': self.role.id,
            'year': 2024,
        }, member=self.member)
        self.assertFalse(form.is_valid())
        self.assertIn('Du har redan lagt till den här funktionärsposten', form.errors['__all__'][0])

    def test_allows_unique_entries(self):
        form = FunctionaryForm(data={
            'functionary_role': self.role.id,
            'year': 2023,
        }, member=self.member)
        self.assertTrue(form.is_valid())
        functionary = form.save(commit=False)
        functionary.member = self.member
        functionary.save()
        self.assertEqual(Functionary.objects.count(), 1)


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.payload = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'supersecret',
            'cf-turnstile-response': 'token',
        }

    @patch('members.views.validate_captcha', return_value=False)
    def test_signup_requires_valid_captcha(self, mock_captcha):
        response = self.client.post(reverse('members:signup'), data=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'members/signup.html')
        self.assertEqual(Member.objects.filter(username='newuser').count(), 0)
        mock_captcha.assert_called_once()

    @patch('members.views.send_email_task')
    @patch('members.views.validate_captcha', return_value=True)
    def test_signup_creates_inactive_user_and_sets_session_flag(self, mock_captcha, mock_send_email):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(reverse('members:signup'), data=self.payload)

        self.assertEqual(response.status_code, 302)
        user = Member.objects.get(username='newuser')
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password('supersecret'))
        self.assertTrue(self.client.session['signup_submitted'])
        mock_captcha.assert_called_once()
        self.assertEqual(len(callbacks), 1)
        mock_send_email.delay.assert_called_once()


class MembersAuthUrlTests(TestCase):
    def test_members_namespace_exposes_login_and_password_change_routes(self):
        self.assertEqual(reverse('members:login'), '/members/login/')
        self.assertEqual(reverse('members:password_change'), '/members/password_change/')


class FunctionaryHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='helper',
            password='pwd',
            membership_type=self.membership_type,
        )
        self.role = FunctionaryRole.objects.create(title='Secretary', board=False)
        Functionary.objects.create(member=self.member, functionary_role=self.role, year=2023)
        Functionary.objects.create(member=self.member, functionary_role=self.role, year=2024)

    def test_get_selected_year_defaults_to_current(self):
        request = self.factory.get('/funktionarer/')
        request.user = self.member
        years = Functionary.objects.values_list('year', flat=True).distinct().order_by('-year')
        selected, all_years = get_selected_year(request, years)
        self.assertEqual(selected, timezone.now().year)
        self.assertFalse(all_years)

    def test_get_selected_year_allows_all_years_filter(self):
        request = self.factory.get('/funktionarer/?year=all')
        request.user = self.member
        years = Functionary.objects.values_list('year', flat=True).distinct().order_by('-year')
        selected, all_years = get_selected_year(request, years)
        self.assertEqual(list(selected), list(years))
        self.assertTrue(all_years)

    def test_get_selected_year_ignores_parameters_for_anonymous_user(self):
        request = self.factory.get('/funktionarer/?year=2020')
        request.user = AnonymousUser()
        years = Functionary.objects.values_list('year', flat=True).distinct().order_by('-year')
        selected, _ = get_selected_year(request, years)
        self.assertEqual(selected, timezone.now().year)

    def test_get_selected_role_supports_all_and_specific_roles(self):
        request_all = self.factory.get('/funktionarer/?role=all')
        request_all.user = self.member
        roles = FunctionaryRole.objects.all()
        selected, all_roles = get_selected_role(request_all, roles)
        self.assertTrue(all_roles)
        self.assertEqual(list(selected), list(roles))

        request_specific = self.factory.get(f'/funktionarer/?role={self.role.title}')
        request_specific.user = self.member
        selected_role, all_roles_flag = get_selected_role(request_specific, roles)
        self.assertFalse(all_roles_flag)
        self.assertEqual(selected_role, self.role)

    def test_get_selected_role_ignores_anonymous_requests(self):
        request = self.factory.get('/funktionarer/?role=all')
        request.user = AnonymousUser()
        roles = FunctionaryRole.objects.all()
        selected, all_roles = get_selected_role(request, roles)
        self.assertIsNone(selected)
        self.assertFalse(all_roles)


class TwoFactorIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='otpuser',
            email='otp@example.com',
            password='secret12345',
            membership_type=self.membership_type,
            first_name='Otp',
            last_name='User',
        )

    def _totp_token(self, device, timestamp=None):
        totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
        totp.time = timestamp or time.time()
        return str(totp.token()).zfill(device.digits)

    def _wizard_prefix(self, response):
        return response.context['wizard']['management_form'].prefix

    def test_login_route_supports_email_then_requires_token(self):
        device = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        response = self.client.get(reverse('members:login'))
        prefix = self._wizard_prefix(response)

        response = self.client.post(reverse('members:login'), data={
            f'{prefix}-current_step': 'auth',
            'auth-username': self.member.email,
            'auth-password': 'secret12345',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['wizard']['steps'].current, 'token')

        prefix = self._wizard_prefix(response)
        response = self.client.post(reverse('members:login'), data={
            f'{prefix}-current_step': 'token',
            'token-otp_token': self._totp_token(device),
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('index'))

    def test_login_redirects_to_safe_referer_when_next_is_missing(self):
        login_url = reverse('members:login')
        response = self.client.get(login_url, HTTP_REFERER='http://testserver/events/?page=2')

        self.assertEqual(response.status_code, 200)
        prefix = self._wizard_prefix(response)

        response = self.client.post(login_url, data={
            f'{prefix}-current_step': 'auth',
            'auth-username': self.member.email,
            'auth-password': 'secret12345',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/events/?page=2')
        self.assertNotIn(INFERRED_REDIRECT_SESSION_KEY, self.client.session)

    def test_login_clears_stale_inferred_redirect_when_referer_is_missing(self):
        login_url = reverse('members:login')
        session = self.client.session
        session[INFERRED_REDIRECT_SESSION_KEY] = '/stale-path/'
        session.save()

        response = self.client.get(login_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(INFERRED_REDIRECT_SESSION_KEY, self.client.session)

    def test_login_ignores_external_referer_and_defaults_to_homepage(self):
        login_url = reverse('members:login')
        response = self.client.get(login_url, HTTP_REFERER='https://evil.example/phish')
        prefix = self._wizard_prefix(response)

        response = self.client.post(login_url, data={
            f'{prefix}-current_step': 'auth',
            'auth-username': self.member.email,
            'auth-password': 'secret12345',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('index'))

    def test_login_page_renders_github_button_with_redirect_target(self):
        with override_settings(
            GITHUB_CLIENT_ID='test-client-id',
            GITHUB_CLIENT_SECRET='test-client-secret',
            GITHUB_REDIRECT_URI='https://example.com/members/github/callback/',
        ):
            response = self.client.get(f"{reverse('members:login')}?next=/events/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="button github-button"', html=False)
        self.assertContains(
            response,
            f'href="{reverse("members:github_login")}?next=/events/"',
            html=False,
        )

    def test_strict_totp_form_saves_device_with_one_step_tolerance(self):
        form_key = '3132333435363738393031323334353637383930'
        current_token = TOTP(bytes.fromhex(form_key)).token()
        form = StrictTOTPDeviceForm(
            key=form_key,
            user=self.member,
            data={'token': current_token},
        )

        self.assertTrue(form.is_valid(), form.errors)
        device = form.save()
        self.assertEqual(device.tolerance, 1)

    def test_setup_view_uses_strict_totp_form_for_generator_method(self):
        view = MemberSetupView()
        with patch('members.two_factor.SetupView.get_form_list', return_value={'generator': TOTPDeviceForm, 'welcome': object}):
            form_list = view.get_form_list()

        self.assertIs(form_list['generator'], StrictTOTPDeviceForm)

    def test_setup_route_renders_strict_totp_form(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('two_factor:setup'))
        prefix = self._wizard_prefix(response)

        response = self.client.post(reverse('two_factor:setup'), data={
            f'{prefix}-current_step': 'welcome',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['wizard']['steps'].current, 'generator')
        self.assertIsInstance(response.context['wizard']['form'], StrictTOTPDeviceForm)

    def test_strict_totp_form_signature_supports_setup_view_kwargs(self):
        form_parameters = signature(StrictTOTPDeviceForm).parameters

        self.assertIn('key', form_parameters)
        self.assertIn('user', form_parameters)

    def test_profile_page_shows_2fa_state(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        response = self.client.get(reverse('members:info'))
        self.assertContains(response, reverse('two_factor:setup'))

        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        response = self.client.get(reverse('members:info'))
        self.assertContains(response, reverse('two_factor:disable'))
        self.assertContains(response, reverse('two_factor:backup_tokens'))

    def test_admin_requires_verified_device(self):
        admin_user = Member.objects.create_superuser(
            username='adminotp',
            email='adminotp@example.com',
            password='secret12345',
            membership_type=self.membership_type,
        )
        device = TOTPDevice.objects.create(user=admin_user, confirmed=True, name='default')

        self.client.force_login(admin_user, backend='members.backends.AuthBackend')
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.headers['Location'])

        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

    def test_admin_login_allows_staff_without_registered_2fa(self):
        admin_user = Member.objects.create_superuser(
            username='adminplain',
            email='adminplain@example.com',
            password='secret12345',
            membership_type=self.membership_type,
        )
        response = self.client.get(f"{reverse('members:login')}?next={reverse('admin:index')}")
        prefix = self._wizard_prefix(response)

        response = self.client.post(f"{reverse('members:login')}?next={reverse('admin:index')}", data={
            f'{prefix}-current_step': 'auth',
            'auth-username': admin_user.email,
            'auth-password': 'secret12345',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('admin:index'))

    def test_setup_complete_redirects_to_saved_next_target(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        device = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session['next'] = reverse('admin:index')
        session.save()

        response = self.client.get(reverse('two_factor:setup_complete'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('admin:index'))
        self.assertNotIn('next', self.client.session)

    def test_setup_complete_ignores_external_redirect_target(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        device = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session['next'] = 'https://evil.example/phish'
        session.save()

        response = self.client.get(reverse('two_factor:setup_complete'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('index'))
        self.assertNotIn('next', self.client.session)

    def test_setup_complete_rejects_insecure_same_host_redirect_on_https(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        device = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session['next'] = 'http://testserver/admin/'
        session.save()

        response = self.client.get(reverse('two_factor:setup_complete'), secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('index'))
        self.assertNotIn('next', self.client.session)

    def test_disable_two_factor_removes_all_devices_for_selected_members(self):
        other = Member.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='secret12345',
            membership_type=self.membership_type,
        )
        totp = TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        static = StaticDevice.objects.create(user=self.member, confirmed=True, name='backup')
        totp_other = TOTPDevice.objects.create(user=other, confirmed=True, name='default')

        admin_user = Member.objects.create_superuser(
            username='admintest',
            email='admintest@example.com',
            password='secret12345',
            membership_type=self.membership_type,
        )
        self.client.force_login(admin_user, backend='members.backends.AuthBackend')

        self.client.post(
            reverse('admin:members_member_changelist'),
            {
                'action': 'disable_two_factor',
                '_selected_action': [self.member.pk],
            },
        )

        self.assertFalse(TOTPDevice.objects.filter(pk=totp.pk).exists())
        self.assertFalse(StaticDevice.objects.filter(pk=static.pk).exists())
        self.assertTrue(TOTPDevice.objects.filter(pk=totp_other.pk).exists())

    def test_invalid_profile_post_keeps_editor_open_with_errors(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        response = self.client.post(reverse('members:info'), data={
            'first_name': '',
            'last_name': self.member.last_name,
            'phone': self.member.phone,
            'address': self.member.address,
            'zip_code': self.member.zip_code,
            'city': self.member.city,
            'country': self.member.country,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_first_name_error', html=False)
        self.assertContains(response, 'id="userInfo" style="display:none;"', html=False)
        self.assertNotContains(response, 'id="editForm" style="display:none;"', html=False)


GITHUB_SETTINGS = {
    'GITHUB_CLIENT_ID': 'test-client-id',
    'GITHUB_CLIENT_SECRET': 'test-client-secret',
    'GITHUB_MFA_POLICY': 'enrolled',
}


def _mock_github_responses(github_id=123, email='ghuser@example.com'):
    """Return (mock_post, mock_get) patchers for the GitHub OAuth API calls."""
    token_resp = MagicMock()
    token_resp.raise_for_status = MagicMock()
    token_resp.json.return_value = {'access_token': 'gh-token-abc'}

    user_resp = MagicMock()
    user_resp.raise_for_status = MagicMock()
    user_resp.json.return_value = {'id': github_id, 'email': email}

    emails_resp = MagicMock()
    emails_resp.raise_for_status = MagicMock()
    emails_resp.json.return_value = [{'email': email, 'verified': True, 'primary': True}]

    mock_post = patch('members.views_github.requests.post', return_value=token_resp)
    mock_get = patch('members.views_github.requests.get', side_effect=[user_resp, emails_resp])
    return mock_post, mock_get


@override_settings(**GITHUB_SETTINGS)
class GitHubLoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)

    def test_redirects_to_github_with_state(self):
        response = self.client.get(reverse('members:github_login'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('github.com/login/oauth/authorize', response['Location'])
        self.assertIn('test-client-id', response['Location'])
        self.assertIn('github_oauth_state', self.client.session)

    def test_stores_next_in_session(self):
        self.client.get(reverse('members:github_login') + '?next=/events/')
        self.assertEqual(self.client.session.get('github_oauth_next'), '/events/')

    def test_does_not_store_next_when_absent(self):
        self.client.get(reverse('members:github_login'))
        self.assertNotIn('github_oauth_next', self.client.session)

    def test_rejects_external_next_url(self):
        self.client.get(reverse('members:github_login') + '?next=https://evil.example/phish')
        self.assertNotIn('github_oauth_next', self.client.session)

    @override_settings(GITHUB_CLIENT_ID='')
    def test_redirects_to_login_when_not_configured(self):
        response = self.client.get(reverse('members:github_login'))
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)


@override_settings(**GITHUB_SETTINGS)
class GitHubCallbackViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='ghuser',
            email='ghuser@example.com',
            password='secret123',
            membership_type=cls.membership_type,
            github_id=999,
        )

    def setUp(self):
        self.client = Client()
        # Prime a valid session state
        session = self.client.session
        session['github_oauth_state'] = 'valid-state'
        session['github_oauth_intent'] = 'login'
        session.save()

    def _callback(self, state='valid-state', code='auth-code', **extra):
        return self.client.get(
            reverse('members:github_callback'),
            {'state': state, 'code': code, **extra},
        )

    def test_state_mismatch_returns_error(self):
        response = self._callback(state='wrong-state')
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)

    def test_missing_code_returns_error(self):
        response = self.client.get(
            reverse('members:github_callback'),
            {'state': 'valid-state'},
        )
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)

    def test_github_error_param_returns_error(self):
        response = self.client.get(
            reverse('members:github_callback'),
            {'error': 'access_denied'},
        )
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)

    def test_successful_login_by_github_id(self):
        mock_post, mock_get = _mock_github_responses(github_id=999)
        with mock_post, mock_get:
            response = self._callback()
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_member_with_two_factor_is_redirected_to_token_step(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        session = self.client.session
        session['github_oauth_next'] = '/events/'
        session.save()

        mock_post, mock_get = _mock_github_responses(github_id=999)
        with mock_post, mock_get:
            response = self._callback()

        self.assertRedirects(
            response,
            f'{reverse("members:login")}?next=%2Fevents%2F',
            fetch_redirect_response=False,
        )
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('github_oauth_next', self.client.session)

        wizard_session = self.client.session['wizard_member_login_view']
        self.assertEqual(wizard_session['step'], 'token')
        self.assertEqual(wizard_session['user_pk'], str(self.member.pk))
        self.assertEqual(wizard_session['user_backend'], 'members.backends.AuthBackend')

    @override_settings(**{**GITHUB_SETTINGS, 'GITHUB_MFA_POLICY': 'off'})
    def test_member_with_two_factor_can_bypass_local_token_when_policy_is_off(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        mock_post, mock_get = _mock_github_responses(github_id=999)

        with mock_post, mock_get:
            response = self._callback()

        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)
        self.assertNotIn('wizard_member_login_view', self.client.session)

    @override_settings(**{**GITHUB_SETTINGS, 'GITHUB_MFA_POLICY': 'staff'})
    def test_non_staff_member_with_two_factor_can_bypass_local_token_when_policy_is_staff(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        mock_post, mock_get = _mock_github_responses(github_id=999)

        with mock_post, mock_get:
            response = self._callback()

        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)
        self.assertNotIn('wizard_member_login_view', self.client.session)

    @override_settings(**{**GITHUB_SETTINGS, 'GITHUB_MFA_POLICY': 'staff'})
    def test_staff_member_with_two_factor_is_redirected_to_token_step_when_policy_is_staff(self):
        staff_member = Member.objects.create_superuser(
            username='ghstaff',
            email='ghstaff@example.com',
            password='secret123',
            membership_type=self.membership_type,
            github_id=1001,
        )
        TOTPDevice.objects.create(user=staff_member, confirmed=True, name='default')
        mock_post, mock_get = _mock_github_responses(github_id=1001, email='ghstaff@example.com')

        with mock_post, mock_get:
            response = self._callback()

        self.assertRedirects(
            response,
            f'{reverse("members:login")}?next=%2Fmembers%2Finfo%2F',
            fetch_redirect_response=False,
        )
        self.assertNotIn('_auth_user_id', self.client.session)
        wizard_session = self.client.session['wizard_member_login_view']
        self.assertEqual(wizard_session['step'], 'token')
        self.assertEqual(wizard_session['user_pk'], str(staff_member.pk))

    @override_settings(**{**GITHUB_SETTINGS, 'GITHUB_MFA_POLICY': 'OFF'})
    def test_policy_value_is_case_insensitive(self):
        TOTPDevice.objects.create(user=self.member, confirmed=True, name='default')
        mock_post, mock_get = _mock_github_responses(github_id=999)

        with mock_post, mock_get:
            response = self._callback()

        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_successful_login_by_email_links_github_id(self):
        member = Member.objects.create_user(
            username='emailonly',
            email='emailonly@example.com',
            password='secret123',
            membership_type=self.membership_type,
        )
        mock_post, mock_get = _mock_github_responses(github_id=777, email='emailonly@example.com')
        with mock_post, mock_get:
            response = self._callback()
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        member.refresh_from_db()
        self.assertEqual(member.github_id, 777)

    def test_no_matching_member_returns_error(self):
        mock_post, mock_get = _mock_github_responses(github_id=404, email='nobody@example.com')
        with mock_post, mock_get:
            response = self._callback()
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_member_cannot_login(self):
        inactive = Member.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='secret123',
            membership_type=self.membership_type,
            github_id=888,
            is_active=False,
        )
        mock_post, mock_get = _mock_github_responses(github_id=888)
        with mock_post, mock_get:
            response = self._callback()
        self.assertRedirects(response, reverse('members:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_next_url_is_honoured_after_login(self):
        session = self.client.session
        session['github_oauth_next'] = '/events/'
        session.save()
        mock_post, mock_get = _mock_github_responses(github_id=999)
        with mock_post, mock_get:
            response = self._callback()
        self.assertRedirects(response, '/events/', fetch_redirect_response=False)

    def test_next_removed_from_session_after_login(self):
        session = self.client.session
        session['github_oauth_next'] = '/events/'
        session.save()
        mock_post, mock_get = _mock_github_responses(github_id=999)
        with mock_post, mock_get:
            self._callback()
        self.assertNotIn('github_oauth_next', self.client.session)


@override_settings(**GITHUB_SETTINGS)
class GitHubConnectViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='connectuser',
            email='connect@example.com',
            password='secret123',
            membership_type=cls.membership_type,
        )
        cls.other = Member.objects.create_user(
            username='otherconnect',
            email='other@example.com',
            password='secret123',
            membership_type=cls.membership_type,
            github_id=555,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def _prime_callback_session(self, github_id):
        session = self.client.session
        session['github_oauth_state'] = 'connect-state'
        session['github_oauth_intent'] = 'connect'
        session.save()
        mock_post, mock_get = _mock_github_responses(github_id=github_id)
        return mock_post, mock_get

    def test_connect_requires_post(self):
        response = self.client.get(reverse('members:github_connect'))
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)

    def test_connect_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('members:github_connect'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('members:login'), response['Location'])

    def test_connect_initiates_oauth_and_stores_intent(self):
        response = self.client.post(reverse('members:github_connect'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('github.com/login/oauth/authorize', response['Location'])
        self.assertEqual(self.client.session['github_oauth_intent'], 'connect')

    def test_callback_links_github_id_to_member(self):
        mock_post, mock_get = self._prime_callback_session(github_id=321)
        with mock_post, mock_get:
            response = self.client.get(
                reverse('members:github_callback'),
                {'state': 'connect-state', 'code': 'code123'},
            )
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.member.refresh_from_db()
        self.assertEqual(self.member.github_id, 321)

    def test_callback_rejects_github_id_already_on_another_member(self):
        mock_post, mock_get = self._prime_callback_session(github_id=555)
        with mock_post, mock_get:
            response = self.client.get(
                reverse('members:github_callback'),
                {'state': 'connect-state', 'code': 'code123'},
            )
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.github_id)


@override_settings(**GITHUB_SETTINGS)
class GitHubDisconnectViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='discuser',
            email='disc@example.com',
            password='secret123',
            membership_type=self.membership_type,
            github_id=111,
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_disconnect_clears_github_id(self):
        response = self.client.post(reverse('members:github_disconnect'))
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.github_id)

    def test_disconnect_requires_post(self):
        response = self.client.get(reverse('members:github_disconnect'))
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        self.member.refresh_from_db()
        self.assertEqual(self.member.github_id, 111)

    def test_disconnect_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('members:github_disconnect'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('members:login'), response['Location'])

    def test_disconnect_with_no_linked_account_shows_error(self):
        self.member.github_id = None
        self.member.save()
        response = self.client.post(reverse('members:github_disconnect'))
        self.assertRedirects(response, reverse('members:info'), fetch_redirect_response=False)
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any('Inget GitHub' in str(m) for m in messages_list))
