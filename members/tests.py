from unittest.mock import patch

import pyotp
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from members.constants import (
    TWO_FACTOR_SETUP_SESSION_KEY,
    TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY,
)
from members.forms import (FunctionaryForm, MemberCreationForm, SignUpForm,
                           SubscriptionPaymentForm)
from members.functionary import get_selected_role, get_selected_year
from members.models import (Functionary, FunctionaryRole, Member,
                            MembershipType, ORDINARY_MEMBER, Subscription)


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


class TwoFactorFlowTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.password = "secret12345"
        self.user = Member.objects.create_user(
            username="twofactor",
            email="twofactor@example.com",
            password=self.password,
            membership_type=self.membership_type,
        )

    def _enable_two_factor(self, user=None):
        user = user or self.user
        secret = pyotp.random_base32()
        user.two_factor_secret = secret
        user.two_factor_enabled_at = timezone.now()
        user.save(update_fields=["two_factor_secret", "two_factor_enabled_at"])
        return secret

    def _mark_two_factor_verified(self, user=None):
        user = user or self.user
        session = self.client.session
        session[TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY] = user.pk
        session.save()

    def test_login_without_two_factor_redirects_directly_to_profile(self):
        response = self.client.post(
            reverse("members:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertRedirects(response, reverse("members:info"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, self.client.session)

    def test_enabled_two_factor_user_is_redirected_to_verification(self):
        self._enable_two_factor()
        response = self.client.post(
            reverse("members:login"),
            {"username": self.user.username, "password": self.password},
        )
        self.assertRedirects(response, reverse("members:info"), fetch_redirect_response=False)

        follow_up = self.client.get(reverse("members:info"))
        self.assertRedirects(
            follow_up,
            f"{reverse('members:two_factor_verify')}?next={reverse('members:info')}",
            fetch_redirect_response=False,
        )

    def test_login_preserves_next_parameter(self):
        login_url = f"{reverse('members:login')}?next=/events/"
        response = self.client.get(login_url)
        self.assertContains(response, 'name="next" value="/events/"')

        post_response = self.client.post(
            login_url,
            {"username": self.user.username, "password": self.password, "next": "/events/"},
        )
        self.assertRedirects(post_response, "/events/", fetch_redirect_response=False)

    def test_two_factor_verification_completes_login(self):
        secret = self._enable_two_factor()
        self.client.post(
            reverse("members:login"),
            {"username": self.user.username, "password": self.password},
        )

        token = pyotp.TOTP(secret).now()
        response = self.client.post(
            reverse("members:two_factor_verify"),
            {"token": token, "next": reverse("members:info")},
        )
        self.assertRedirects(response, reverse("members:info"))
        self.assertEqual(self.client.session[TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY], self.user.pk)

        profile_response = self.client.get(reverse("members:info"))
        self.assertEqual(profile_response.status_code, 200)

    def test_invalid_two_factor_code_keeps_user_unverified(self):
        self._enable_two_factor()
        self.client.post(
            reverse("members:login"),
            {"username": self.user.username, "password": self.password},
        )

        response = self.client.post(
            reverse("members:two_factor_verify"),
            {"token": "000000", "next": reverse("members:info")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Felaktig verifieringskod")
        self.assertNotIn(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, self.client.session)

    def test_previous_totp_window_is_rejected(self):
        secret = self._enable_two_factor()
        self.client.post(
            reverse("members:login"),
            {"username": self.user.username, "password": self.password},
        )

        now = timezone.now().timestamp()
        expired_token = pyotp.TOTP(secret).at(now - 30)
        response = self.client.post(
            reverse("members:two_factor_verify"),
            {"token": expired_token, "next": reverse("members:info")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Felaktig verifieringskod")
        self.assertNotIn(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, self.client.session)

    def test_user_can_enable_two_factor_after_confirming_token(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("members:two_factor_settings"),
            {"action": "start_setup"},
        )
        self.assertRedirects(response, reverse("members:two_factor_settings"))

        setup_secret = self.client.session[TWO_FACTOR_SETUP_SESSION_KEY]
        token = pyotp.TOTP(setup_secret).now()
        confirm_response = self.client.post(
            reverse("members:two_factor_settings"),
            {"action": "confirm_setup", "token": token},
        )
        self.assertRedirects(confirm_response, reverse("members:info"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.has_2fa_enabled)
        self.assertEqual(self.client.session[TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY], self.user.pk)
        self.assertNotIn(TWO_FACTOR_SETUP_SESSION_KEY, self.client.session)

    def test_user_can_disable_two_factor_with_password_and_token(self):
        secret = self._enable_two_factor()
        self.client.force_login(self.user)
        self._mark_two_factor_verified()

        response = self.client.post(
            reverse("members:two_factor_settings"),
            {"action": "disable", "password": self.password, "token": pyotp.TOTP(secret).now()},
        )
        self.assertRedirects(response, reverse("members:info"))

        self.user.refresh_from_db()
        self.assertFalse(self.user.has_2fa_enabled)
        self.assertNotIn(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, self.client.session)

    def test_force_login_clears_existing_two_factor_session_state(self):
        self._enable_two_factor()
        self._mark_two_factor_verified()

        other_user = Member.objects.create_user(
            username="other-twofactor",
            email="other@example.com",
            password=self.password,
            membership_type=self.membership_type,
        )
        self.client.force_login(other_user)

        self.assertNotIn(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, self.client.session)

    def test_admin_requires_two_factor_after_login(self):
        self._enable_two_factor(
            Member.objects.create_superuser(
                username="admin2fa",
                password=self.password,
                email="admin2fa@example.com",
            )
        )
        response = self.client.post(
            reverse("admin:login"),
            {"username": "admin2fa", "password": self.password},
        )
        self.assertEqual(response.status_code, 302)

        admin_response = self.client.get(reverse("admin:index"))
        self.assertRedirects(
            admin_response,
            f"{reverse('members:two_factor_verify')}?next={reverse('admin:index')}",
            fetch_redirect_response=False,
        )

    def test_admin_logout_is_exempt_from_two_factor_redirect(self):
        self._enable_two_factor(
            Member.objects.create_superuser(
                username="adminlogout",
                password=self.password,
                email="adminlogout@example.com",
            )
        )
        self.client.post(
            reverse("admin:login"),
            {"username": "adminlogout", "password": self.password},
        )

        response = self.client.post(reverse("admin:logout"))
        self.assertEqual(response.status_code, 302)
