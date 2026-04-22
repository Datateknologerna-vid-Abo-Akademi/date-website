from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Member, MembershipType, ORDINARY_MEMBER, Subscription, SubscriptionPayment


class MemberAdminSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.admin_user = Member.objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@example.com",
            membership_type=cls.membership_type,
        )
        cls.member = Member.objects.create_user(
            username="ada_lovelace",
            password="pass",
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            phone="+358 50 123 4567",
            address="Algorithm Alley 1",
            zip_code="20500",
            city="Turku",
            country="Finland",
            membership_type=cls.membership_type,
            year_of_admission=1843,
            github_id=424242,
        )
        cls.group = Group.objects.create(name="board")
        cls.member.groups.add(cls.group)
        cls.subscription = Subscription.objects.create(
            name="Lifetime membership",
            does_expire=False,
            renewal_scale="year",
            renewal_period=1,
            price=0,
        )
        SubscriptionPayment.objects.create(
            member=cls.member,
            subscription=cls.subscription,
            date_paid=timezone.now().date(),
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def assert_member_search_finds_member(self, query):
        response = self.client.get(reverse("admin:members_member_changelist"), {"q": query})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ada_lovelace")

    def test_member_search_handles_common_identifiers(self):
        for query in [
            "Ada Lovelace",
            "Lovelace Ada",
            "ada@example.com",
            "ada_lovelace",
            "0501234567",
            "1843",
            "424242",
            "20500",
            "Turku",
            "Ordinarie",
            "board",
            "Lifetime",
        ]:
            with self.subTest(query=query):
                self.assert_member_search_finds_member(query)
