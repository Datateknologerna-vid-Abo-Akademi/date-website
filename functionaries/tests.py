from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.utils import timezone

from functionaries.forms import FunctionaryForm
from functionaries.models import Functionary, FunctionaryRole
from functionaries.selectors import get_selected_role, get_selected_year
from members.models import Member, MembershipType, ORDINARY_MEMBER


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

    def test_snapshots_member_name_for_deleted_member_display(self):
        self.member.first_name = 'Function'
        self.member.last_name = 'Ary'
        self.member.save()
        functionary = Functionary.objects.create(
            member=self.member,
            functionary_role=self.role,
            year=2024,
        )

        self.member.delete()
        functionary.refresh_from_db()

        self.assertIsNone(functionary.member)
        self.assertEqual(functionary.name, 'Function Ary')
        self.assertEqual(functionary.get_full_name(), 'Function Ary')

    def test_uses_username_when_member_name_is_blank(self):
        functionary = Functionary.objects.create(
            member=self.member,
            functionary_role=self.role,
            year=2024,
        )

        self.assertEqual(functionary.name, 'functionary')


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
