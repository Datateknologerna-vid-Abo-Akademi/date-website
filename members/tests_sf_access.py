from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from members.admin import UserAdmin
from members.forms import AdminMemberUpdateForm, MemberCreationForm, SignUpForm
from members.models import ORDINARY_MEMBER, Member, MembershipType, Subscription
from members.provisioning import provision_membership_access

SF_SETTINGS = {
    'MEMBERSHIP_TYPE_NAMES': ('Ordinarie medlem', 'Evig SF:are'),
    'MEMBERS_SIGNUP_FIELDS': (
        'username',
        'email',
        'first_name',
        'last_name',
        'city',
        'membership_type',
        'year_of_admission',
        'password',
    ),
    'MEMBERS_SIGNUP_DEFAULT_MEMBERSHIP_TYPE': 'Ordinarie medlem',
    'MEMBERS_SIGNUP_CITY_LABEL': 'Hemort',
    'MEMBERSHIP_SUBSCRIPTIONS': {
        'Ordinarie medlem': {
            'price': '15.00',
            'does_expire': True,
            'renewal_scale': 'year',
            'renewal_period': 1,
        },
        'Evig SF:are': {
            'price': '40.00',
            'does_expire': False,
            'renewal_scale': None,
            'renewal_period': None,
        },
    },
    'ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY': True,
    'MEMBER_ADMIN_RESTRICTED_GROUP': 'Inauta',
    'MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE': 'Evig SF:are',
    'SF_ROLE_PERMISSION_SCOPES': {
        'styrelse': 'all_except_members',
        'skattis': 'all',
        'sekre': 'all',
        'Inauta': 'all_with_lifetime_members',
        'webbansvarig': 'all',
        'admin': 'all',
    },
}


@override_settings(**SF_SETTINGS)
class SFSignupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        MembershipType.objects.update_or_create(name='Evig SF:are', defaults={'permission_profile': ORDINARY_MEMBER})

    def test_signup_exposes_only_sf_public_fields(self):
        form = SignUpForm()
        self.assertEqual(
            tuple(form.fields),
            (
                'username',
                'email',
                'first_name',
                'last_name',
                'city',
                'membership_type',
                'year_of_admission',
                'password',
            ),
        )
        self.assertEqual(str(form.fields['city'].label), 'Hemort')
        self.assertEqual(
            set(form.fields['membership_type'].queryset.values_list('name', flat=True)),
            {'Ordinarie medlem', 'Evig SF:are'},
        )

    def test_admin_membership_choices_are_limited_to_sf_types(self):
        expected = {'Ordinarie medlem', 'Evig SF:are'}
        self.assertEqual(
            set(MemberCreationForm().fields['membership_type'].queryset.values_list('name', flat=True)), expected
        )
        self.assertEqual(
            set(AdminMemberUpdateForm().fields['membership_type'].queryset.values_list('name', flat=True)), expected
        )

    def test_admin_forms_expose_gulispass_checkbox(self):
        self.assertIn('archive_access_eligible', MemberCreationForm().fields)
        self.assertIn('archive_access_eligible', AdminMemberUpdateForm().fields)

    @patch('members.views.validate_captcha', return_value=True)
    def test_signup_saves_inactive_member_with_chosen_sf_type(self, _validate_captcha):
        ordinary = MembershipType.objects.get(name='Ordinarie medlem')
        lifetime = MembershipType.objects.create(name='Evig SF:are', permission_profile=ORDINARY_MEMBER)

        response = self.client.post(
            reverse('members:signup'),
            {
                'username': 'new-sf-member',
                'email': 'new@example.com',
                'first_name': 'New',
                'last_name': 'Member',
                'city': 'Åbo',
                'membership_type': lifetime.id,
                'year_of_admission': 2026,
                'password': 'safe-password',
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(username='new-sf-member')
        self.assertEqual(member.membership_type, lifetime)
        self.assertFalse(member.is_active)
        self.assertEqual(member.city, 'Åbo')
        self.assertNotEqual(member.membership_type, ordinary)


@override_settings(**SF_SETTINGS)
class SFProvisioningTests(TestCase):
    def test_provisioning_is_repeatable_and_assigns_role_permissions(self):
        legacy_type = MembershipType.objects.create(name='Legacy type', permission_profile=ORDINARY_MEMBER)
        duplicate = MembershipType.objects.create(name='Evig SF:are', permission_profile=1)
        provision_membership_access()
        provision_membership_access()

        self.assertTrue(MembershipType.objects.filter(pk=legacy_type.pk).exists())
        self.assertEqual(MembershipType.objects.get(name='Ordinarie medlem').permission_profile, ORDINARY_MEMBER)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.permission_profile, ORDINARY_MEMBER)
        annual = Subscription.objects.get(name='Ordinarie medlem')
        lifetime = Subscription.objects.get(name='Evig SF:are')
        self.assertEqual(str(annual.price), '15.00')
        self.assertEqual((annual.does_expire, annual.renewal_scale, annual.renewal_period), (True, 'year', 1))
        self.assertEqual(str(lifetime.price), '40.00')
        self.assertEqual((lifetime.does_expire, lifetime.renewal_scale, lifetime.renewal_period), (False, None, None))
        expected_groups = set(SF_SETTINGS['SF_ROLE_PERMISSION_SCOPES'])
        self.assertEqual(
            expected_groups,
            set(Group.objects.values_list('name', flat=True)) & expected_groups,
        )

        member_permissions = Permission.objects.filter(content_type__app_label='members')
        self.assertFalse(Group.objects.get(name='styrelse').permissions.filter(pk__in=member_permissions).exists())
        for group_name in ('skattis', 'sekre', 'webbansvarig', 'admin'):
            self.assertEqual(
                set(Group.objects.get(name=group_name).permissions.values_list('pk', flat=True)),
                set(Group.objects.get(name='skattis').permissions.values_list('pk', flat=True)),
            )
        inauta_permissions = Group.objects.get(name='Inauta').permissions
        self.assertEqual(
            set(inauta_permissions.filter(content_type__app_label='members').values_list('codename', flat=True)),
            {'view_member', 'change_member', 'delete_member'},
        )


@override_settings(**SF_SETTINGS)
class SFMemberAdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ordinary = MembershipType.objects.get(name='Ordinarie medlem')
        cls.lifetime = MembershipType.objects.create(name='Evig SF:are', permission_profile=ORDINARY_MEMBER)
        cls.inauta = Member.objects.create_user(username='inauta', password='pwd', membership_type=cls.ordinary)
        cls.inauta.groups.add(Group.objects.create(name='Inauta'))
        cls.ordinary_member = Member.objects.create_user(
            username='ordinary-target', password='pwd', membership_type=cls.ordinary
        )
        cls.lifetime_member = Member.objects.create_user(
            username='lifetime-target', password='pwd', membership_type=cls.lifetime
        )

    def setUp(self):
        self.model_admin = UserAdmin(Member, admin.site)
        self.request = RequestFactory().get('/admin/members/member/')
        self.request.user = self.inauta

    def test_inauta_queryset_contains_only_lifetime_members(self):
        self.assertEqual(list(self.model_admin.get_queryset(self.request)), [self.lifetime_member])

    def test_inauta_object_access_is_limited_to_lifetime_members(self):
        self.assertFalse(self.model_admin.has_change_permission(self.request, self.ordinary_member))
        self.assertTrue(self.model_admin._has_restricted_object_access(self.request, self.lifetime_member))

    def test_inauta_cannot_add_members_or_change_membership_type(self):
        self.assertFalse(self.model_admin.has_add_permission(self.request))
        readonly_fields = self.model_admin.get_readonly_fields(self.request, self.lifetime_member)
        self.assertIn('membership_type', readonly_fields)
        self.assertIn('groups', readonly_fields)

    def test_superuser_keeps_unrestricted_queryset(self):
        self.request.user = Member.objects.create_superuser(
            username='root', password='pwd', membership_type=self.ordinary
        )
        self.assertEqual(self.model_admin.get_queryset(self.request).count(), Member.objects.count())
