"""Focused tests for the member admin performance changes."""

import importlib

from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.db_operations import AddIndexConcurrently
from members.models import (
    ORDINARY_MEMBER,
    Member,
    MembershipType,
    Subscription,
    SubscriptionPayment,
)

STAFF_GROUP = "perf-payment-editors"


class MemberAdminTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(permission_profile=ORDINARY_MEMBER)
        cls.admin_user = Member.objects.create_superuser(
            username="perf-admin",
            password="pass",
            email="perf-admin@example.com",
            membership_type=cls.membership_type,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def member_search(self, query):
        response = self.client.get(reverse("admin:members_member_changelist"), {"q": query})
        self.assertEqual(response.status_code, 200)
        return response, list(response.context["cl"].result_list)


class MemberToManySearchTests(MemberAdminTestCase):
    def test_group_search_matches_without_duplicating_the_member(self):
        member = Member.objects.create_user(
            username="group-search-member",
            password="pass",
            email="group-search@example.com",
            first_name="Group",
            last_name="Searcher",
            membership_type=self.membership_type,
        )
        member.groups.add(Group.objects.create(name="board"), Group.objects.create(name="board-alumni"))

        response, results = self.member_search("board")

        self.assertEqual([result.pk for result in results], [member.pk])
        self.assertContains(response, "group-search-member")

    def test_subscription_search_matches_without_duplicating_the_member(self):
        member = Member.objects.create_user(
            username="sub-search-member",
            password="pass",
            email="subscription-search@example.com",
            first_name="Subscription",
            last_name="Searcher",
            membership_type=self.membership_type,
        )
        for name in ("Lifetime membership", "Lifetime supporter"):
            subscription = Subscription.objects.create(
                name=name,
                does_expire=False,
                renewal_scale=None,
                renewal_period=None,
                price=0,
            )
            SubscriptionPayment.objects.create(
                member=member,
                subscription=subscription,
                date_paid=timezone.now().date(),
            )

        response, results = self.member_search("Lifetime")

        self.assertEqual([result.pk for result in results], [member.pk])
        self.assertContains(response, "sub-search-member")

    def test_group_and_subscription_terms_still_combine_with_text_terms(self):
        member = Member.objects.create_user(
            username="combo-search-member",
            password="pass",
            email="combined-search@example.com",
            first_name="Combined",
            last_name="Searcher",
            membership_type=self.membership_type,
        )
        member.groups.add(Group.objects.create(name="combined-board"))
        subscription = Subscription.objects.create(
            name="combined-lifetime",
            does_expire=False,
            renewal_scale=None,
            renewal_period=None,
            price=0,
        )
        SubscriptionPayment.objects.create(
            member=member,
            subscription=subscription,
            date_paid=timezone.now().date(),
        )

        response, results = self.member_search("Combined combined-board")

        self.assertEqual([result.pk for result in results], [member.pk])
        self.assertContains(response, "combo-search-member")


class MemberStringTests(TestCase):
    def test_full_name_when_both_names_are_set(self):
        member = Member(username="ada", first_name="Ada", last_name="Lovelace")

        self.assertEqual(str(member), "Ada Lovelace")

    def test_username_fallback_when_a_name_is_missing(self):
        self.assertEqual(str(Member(username="ada", first_name="Ada", last_name="")), "ada")
        self.assertEqual(str(Member(username="ada", first_name="", last_name="Lovelace")), "ada")


class SubscriptionPaymentAutocompleteTests(MemberAdminTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.payment_member = Member.objects.create_user(
            username="payment-member",
            password="pass",
            email="payment-member@example.com",
            first_name="Payment",
            last_name="Member",
            membership_type=cls.membership_type,
        )
        cls.subscription = Subscription.objects.create(
            name="Payment subscription",
            does_expire=False,
            renewal_scale=None,
            renewal_period=None,
            price=0,
        )
        for index in range(25):
            Member.objects.create_user(
                username=f"pay-option-{index:03d}",
                password="pass",
                email=f"pay-option-{index:03d}@example.com",
                first_name="Pay",
                last_name=f"Option {index:03d}",
                membership_type=cls.membership_type,
            )

    def test_payment_form_renders_member_autocomplete_not_all_members(self):
        response = self.client.get(reverse("admin:members_subscriptionpayment_add"))

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        widget = form.fields["member"].widget
        self.assertIsInstance(getattr(widget, "widget", widget), AutocompleteSelect)
        self.assertContains(response, 'data-field-name="member"')
        self.assertNotContains(response, "pay-option-000")

    def test_change_form_renders_member_autocomplete(self):
        payment = SubscriptionPayment.objects.create(
            member=self.payment_member,
            subscription=self.subscription,
            date_paid=timezone.now().date(),
        )

        response = self.client.get(reverse("admin:members_subscriptionpayment_change", args=[payment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-field-name="member"')
        self.assertContains(response, "Payment Member")
        self.assertNotContains(response, "pay-option-000")

    def test_member_autocomplete_labels_members_with_their_full_name(self):
        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "members",
                "model_name": "subscriptionpayment",
                "field_name": "member",
                "term": "Payment Member",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {"id": str(self.payment_member.pk), "text": "Payment Member"},
            response.json()["results"],
        )

    def test_payment_form_saves_the_selected_member(self):
        response = self.client.post(
            reverse("admin:members_subscriptionpayment_add"),
            {
                "member": self.payment_member.pk,
                "subscription": self.subscription.pk,
                "date_paid": timezone.now().date().isoformat(),
                "amount_paid": "10.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        payment = SubscriptionPayment.objects.get(member=self.payment_member)
        self.assertEqual(payment.subscription, self.subscription)


@override_settings(STAFF_GROUPS=[STAFF_GROUP])
class SubscriptionPaymentAutocompletePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        membership_type = MembershipType.objects.get(permission_profile=ORDINARY_MEMBER)
        editor_group = Group.objects.create(name=STAFF_GROUP)
        cls.editor = Member.objects.create_user(
            username="payment-editor",
            password="pass",
            email="payment-editor@example.com",
            membership_type=membership_type,
        )
        cls.editor.groups.add(editor_group)
        cls.editor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="members",
                codename="change_subscriptionpayment",
            )
        )
        cls.searchable = Member.objects.create_user(
            username="searchable-member",
            password="pass",
            email="searchable@example.com",
            first_name="Searchable",
            last_name="Member",
            membership_type=membership_type,
        )

    def test_payment_editor_can_search_members_without_member_permissions(self):
        self.assertFalse(self.editor.has_perm("members.view_member"))
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "members",
                "model_name": "subscriptionpayment",
                "field_name": "member",
                "term": "Searchable",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {"id": str(self.searchable.pk), "text": "Searchable Member"},
            response.json()["results"],
        )


class PermissionAdminSelectRelatedTests(TestCase):
    def test_permission_changelist_selects_related_content_type(self):
        model_admin = admin.site._registry[Permission]

        self.assertEqual(model_admin.list_select_related, ("content_type",))


class SubscriptionPaymentIndexTests(TestCase):
    def test_date_paid_index_is_declared_on_the_model(self):
        index = next(
            (candidate for candidate in SubscriptionPayment._meta.indexes if candidate.name == "subpayment_date_idx"),
            None,
        )

        self.assertIsNotNone(index)
        self.assertEqual(index.fields, ["date_paid"])

    def test_migration_creates_the_index_concurrently(self):
        migration = importlib.import_module("members.migrations.0018_subscriptionpayment_subpayment_date_idx")
        operation = migration.Migration.operations[0]

        self.assertFalse(migration.Migration.atomic)
        self.assertIsInstance(operation, AddIndexConcurrently)
        self.assertEqual(operation.index.name, "subpayment_date_idx")
        self.assertEqual(operation.index.fields, ["date_paid"])
