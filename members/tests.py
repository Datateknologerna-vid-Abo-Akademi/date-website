import time
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from members.forms import (FunctionaryForm, MemberCreationForm, SignUpForm,
                           SubscriptionPaymentForm)
from members.functionary import get_selected_role, get_selected_year
from members.models import (Functionary, FunctionaryRole, Member,
                            MembershipType, ORDINARY_MEMBER, Subscription)
from members.two_factor import StrictTOTPDeviceForm


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
        response = self.client.post(reverse('members:signup'), data=self.payload)
        self.assertEqual(response.status_code, 302)
        user = Member.objects.get(username='newuser')
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password('supersecret'))
        self.assertTrue(self.client.session['signup_submitted'])
        mock_captcha.assert_called_once()
        mock_send_email.delay.assert_called_once()


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
        response = self.client.get(reverse('login'))
        prefix = self._wizard_prefix(response)

        response = self.client.post(reverse('login'), data={
            f'{prefix}-current_step': 'auth',
            'auth-username': self.member.email,
            'auth-password': 'secret12345',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['wizard']['steps'].current, 'token')

        prefix = self._wizard_prefix(response)
        response = self.client.post(reverse('login'), data={
            f'{prefix}-current_step': 'token',
            'token-otp_token': self._totp_token(device),
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('members:info'))

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
        response = self.client.get(f"{reverse('login')}?next={reverse('admin:index')}")
        prefix = self._wizard_prefix(response)

        response = self.client.post(f"{reverse('login')}?next={reverse('admin:index')}", data={
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
