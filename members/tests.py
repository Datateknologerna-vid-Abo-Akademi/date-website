from unittest.mock import patch

from django.contrib.admin.sites import site
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django import forms

from members.admin import FunctionaryRoleAdmin
from members.forms import (FunctionaryForm, MemberCreationForm, SignUpForm,
                           SubscriptionPaymentForm)
from members.functionary import get_selected_role, get_selected_year, get_filtered_functionaries
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
            'membership_type': cls.membership_type.id,
            'password': 'secret123',
        })
        self.assertTrue(form.is_valid())

    def test_member_creation_form_rejects_invalid_username(self):
        form = MemberCreationForm(data={
            'username': 'invalid user',
            'email': 'user@example.com',
            'first_name': 'Invalid',
            'last_name': 'User',
            'membership_type': cls.membership_type.id,
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
            'membership_type': cls.membership_type.id,
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
            'membership_type': cls.membership_type.id,
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


class FunctionaryRoleAdminTests(TestCase):
    def test_list_filter_fields_exist_on_functionary_role(self):
        admin_instance = FunctionaryRoleAdmin(FunctionaryRole, site)
        for field_name in admin_instance.list_filter:
            try:
                FunctionaryRole._meta.get_field(field_name)
            except FieldDoesNotExist as exc:
                self.fail(f"FunctionaryRoleAdmin list_filter contains invalid field '{field_name}': {exc}")


class FunctionaryRoleAdminIntegrationTests(TestCase):
    def test_admin_system_check_passes(self):
        try:
            call_command('check', 'admin', verbosity=0)
        except SystemCheckError as exc:
            self.fail(f"Django admin system check failed: {exc}")


class FunctionaryRoleAdminButtonTests(TestCase):
    def setUp(self):
        self.admin = FunctionaryRoleAdmin(FunctionaryRole, site)
        self.factory = RequestFactory()

    def test_admin_form_has_board_and_tutor_checkboxes(self):
        form = self.admin.get_form(self.factory.get('/admin/'))()
        self.assertIn('board', form.fields)
        self.assertIn('tutor', form.fields)
        self.assertIsInstance(form.fields['board'].widget, forms.CheckboxInput)
        self.assertIsInstance(form.fields['tutor'].widget, forms.CheckboxInput)

    def test_admin_form_renders_checkboxes(self):
        form = self.admin.get_form(self.factory.get('/admin/'))()
        html = form.as_p()
        self.assertIn('name="board"', html)
        self.assertIn('type="checkbox"', html)
        self.assertIn('name="tutor"', html)
        self.assertIn('type="checkbox"', html)


class FunctionaryRoleTutorFieldTests(TestCase):
    def test_tutor_field_defaults_to_false(self):
        role = FunctionaryRole.objects.create(title='SomeRole')
        self.assertFalse(role.tutor)

    def test_tutor_field_can_be_set_true(self):
        role = FunctionaryRole.objects.create(title='TutorRole', tutor=True)
        self.assertTrue(role.tutor)

    def test_board_and_tutor_can_both_be_true(self):
        role = FunctionaryRole.objects.create(title='BoardTutor', board=True, tutor=True)
        self.assertTrue(role.board)
        self.assertTrue(role.tutor)

    def test_tutor_field_exists_on_model(self):
        FunctionaryRole._meta.get_field('tutor')


class FunctionarySiteBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='funktionar',
            password='pwd',
            membership_type=membership_type,
        )
        cls.other_member = Member.objects.create_user(
            username='annanfunktionar',
            password='pwd',
            membership_type=membership_type,
        )
        cls.board_role = FunctionaryRole.objects.create(title='President', board=True, tutor=False)
        cls.tutor_role = FunctionaryRole.objects.create(title='Tutor', board=False, tutor=True)
        cls.other_role = FunctionaryRole.objects.create(title='Webmaster', board=False, tutor=False)
        cls.board_tutor_role = FunctionaryRole.objects.create(title='Tutor Chair', board=True, tutor=True)

        cls.board_functionary = Functionary.objects.create(
            member=cls.member,
            functionary_role=cls.board_role,
            year=2026,
        )
        cls.tutor_functionary = Functionary.objects.create(
            member=cls.member,
            functionary_role=cls.tutor_role,
            year=2026,
        )
        cls.other_functionary = Functionary.objects.create(
            member=cls.member,
            functionary_role=cls.other_role,
            year=2026,
        )
        cls.board_tutor_functionary = Functionary.objects.create(
            member=cls.member,
            functionary_role=cls.board_tutor_role,
            year=2026,
        )
        cls.previous_year_tutor = Functionary.objects.create(
            member=cls.member,
            functionary_role=cls.tutor_role,
            year=2025,
        )
        cls.foreign_functionary = Functionary.objects.create(
            member=cls.other_member,
            functionary_role=cls.other_role,
            year=2026,
        )


class GetFilteredFunctionariesTests(FunctionarySiteBase):
    def test_board_filter_returns_board_roles_only(self):
        result = get_filtered_functionaries(year=2026, selected_role=None, is_board=True, is_tutor=False)
        self.assertQuerysetEqual(
            result,
            [self.board_functionary, self.board_tutor_functionary],
            transform=lambda obj: obj,
            ordered=False,
        )

    def test_tutor_filter_excludes_roles_that_are_also_board(self):
        result = get_filtered_functionaries(year=2026, selected_role=None, is_board=False, is_tutor=True)
        self.assertQuerysetEqual(
            result,
            [self.tutor_functionary],
            transform=lambda obj: obj,
            ordered=False,
        )

    def test_other_filter_excludes_board_and_tutor_roles(self):
        result = get_filtered_functionaries(year=2026, selected_role=None, is_board=False, is_tutor=False)
        self.assertQuerysetEqual(
            result,
            [self.other_functionary, self.foreign_functionary],
            transform=lambda obj: obj,
            ordered=False,
        )

    def test_year_queryset_includes_multiple_years(self):
        years = Functionary.objects.values_list('year', flat=True).distinct().order_by('-year')
        result = get_filtered_functionaries(year=years, selected_role=self.tutor_role, is_board=False, is_tutor=True)
        self.assertQuerysetEqual(
            result,
            [self.tutor_functionary, self.previous_year_tutor],
            transform=lambda obj: obj,
            ordered=False,
        )

    def test_role_queryset_limits_tutor_results(self):
        roles = FunctionaryRole.objects.filter(tutor=True, board=False)
        result = get_filtered_functionaries(year=2026, selected_role=roles, is_board=False, is_tutor=True)
        self.assertQuerysetEqual(result, [self.tutor_functionary], transform=lambda obj: obj, ordered=False)


class FunctionaryManagementViewTests(FunctionarySiteBase):
    def setUp(self):
        self.client = Client()

    def test_requires_login(self):
        response = self.client.get(reverse('members:functionary'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('members:functionary'), response.url)

    def test_get_shows_only_logged_in_members_functionaries(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('members:functionary'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'members/functionary.html')
        self.assertQuerysetEqual(
            response.context['functionaries'],
            [self.board_functionary, self.tutor_functionary, self.other_functionary, self.board_tutor_functionary, self.previous_year_tutor],
            transform=lambda obj: obj,
            ordered=True,
        )
        self.assertEqual(response.context['user'], self.member)

    def test_post_add_functionary_creates_record_for_logged_in_user(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('members:functionary'), data={
            'add_functionary': '1',
            'functionary_role': self.other_role.id,
            'year': 2024,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Functionary.objects.filter(member=self.member, functionary_role=self.other_role, year=2024).exists()
        )

    def test_post_add_duplicate_functionary_rerenders_form_with_error(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('members:functionary'), data={
            'add_functionary': '1',
            'functionary_role': self.board_role.id,
            'year': 2026,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'members/functionary.html')
        self.assertIn('Du har redan lagt till den här funktionärsposten', response.context['form'].errors['__all__'][0])

    def test_post_delete_functionary_deletes_own_record(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('members:functionary'), data={
            'delete_functionary': '1',
            'functionary_id': self.previous_year_tutor.id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Functionary.objects.filter(pk=self.previous_year_tutor.pk).exists())

    def test_post_delete_functionary_cannot_delete_other_members_record(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('members:functionary'), data={
            'delete_functionary': '1',
            'functionary_id': self.foreign_functionary.id,
        })

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Functionary.objects.filter(pk=self.foreign_functionary.pk).exists())


class FunctionariesViewTests(FunctionarySiteBase):
    def setUp(self):
        self.client = Client()

    def _get_response(self, params=''):
        return self.client.get(reverse('members:functionaries') + params)

    def test_response_has_expected_context_keys(self):
        response = self._get_response()
        self.assertEqual(response.status_code, 200)
        for key in (
            'board_functionaries_by_role',
            'tutor_functionaries_by_role',
            'functionaries_by_role',
            'distinct_years',
            'functionary_roles',
            'selected_role',
            'all_roles',
            'selected_year',
            'all_years',
        ):
            self.assertIn(key, response.context, f'Missing context key: {key}')

    def test_view_splits_functionaries_into_board_tutor_and_other_sections(self):
        response = self._get_response('?year=2026')
        context = response.context

        self.assertIn(self.board_role, context['board_functionaries_by_role'])
        self.assertIn(self.board_tutor_role, context['board_functionaries_by_role'])
        self.assertIn(self.tutor_role, context['tutor_functionaries_by_role'])
        self.assertIn(self.other_role, context['functionaries_by_role'])

        self.assertNotIn(self.tutor_role, context['board_functionaries_by_role'])
        self.assertNotIn(self.board_tutor_role, context['tutor_functionaries_by_role'])
        self.assertNotIn(self.board_role, context['functionaries_by_role'])

    def test_authenticated_user_can_filter_by_specific_role(self):
        self.client.force_login(self.member)
        response = self._get_response(f'?year=2026&role={self.tutor_role.title}')
        context = response.context

        self.assertEqual(context['selected_role'], self.tutor_role)
        self.assertEqual(list(context['tutor_functionaries_by_role'].keys()), [self.tutor_role])
        self.assertEqual(context['board_functionaries_by_role'], {})
        self.assertEqual(context['functionaries_by_role'], {})

    def test_authenticated_user_can_filter_all_years(self):
        self.client.force_login(self.member)
        response = self._get_response('?year=all&role=Tutor')
        grouped_tutors = response.context['tutor_functionaries_by_role'][self.tutor_role]

        self.assertTrue(response.context['all_years'])
        self.assertEqual(response.context['selected_year'], 'Alla År')
        self.assertEqual({functionary.year for functionary in grouped_tutors}, {2025, 2026})

    def test_anonymous_user_query_parameters_are_ignored(self):
        response = self._get_response(f'?year=all&role={self.tutor_role.title}')

        self.assertFalse(response.context['all_years'])
        self.assertIsNone(response.context['selected_role'])
