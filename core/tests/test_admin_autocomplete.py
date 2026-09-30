"""Autocomplete access for editors of the object that owns the related field.

Django's ``AutocompleteJsonView`` only answers when the user holds view
permission on the *related* model. Several admins here point at
``members.Member`` (and ``events.EventAttendees``) through ``autocomplete_fields``
while their editors are deliberately not trusted with the full member registry,
which left those dropdowns empty. ``core.admin.ReferringObjectAutocompleteJsonView``
also accepts the request when the user may add/change the referring object.
"""

import json

from django.contrib import admin as django_admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.admin import ReferringObjectAutocompleteJsonView
from ctf.admin import FlagInline
from ctf.models import Ctf, Flag, Guess
from events.models import Event, EventAttendees
from members.models import ORDINARY_MEMBER, Member, MembershipType

AUTOCOMPLETE_URL = reverse("admin:autocomplete")
STAFF_GROUP = "content-editors"
RESTRICTED_GROUP = "restricted-editors"
RESTRICTED_MEMBERSHIP_TYPE = "Lifetime member"


class _AutocompleteHelpersMixin:
    def _editor(self, *perms):
        user = Member.objects.create_user(
            username=f"editor_{self._testMethodName}"[:20],
            email=f"{self._testMethodName}@example.com",
        )
        user.groups.add(self.group)
        for app_label, codename in perms:
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return user

    def _results(self, app_label, model_name, field_name, term="ada"):
        response = self.client.get(
            AUTOCOMPLETE_URL,
            {
                "app_label": app_label,
                "model_name": model_name,
                "field_name": field_name,
                "term": term,
            },
        )
        if response.status_code != 200:
            return response.status_code, []
        return 200, json.loads(response.content)["results"]


@override_settings(STAFF_GROUPS=[STAFF_GROUP])
class ReferringObjectAutocompleteTests(_AutocompleteHelpersMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = Member.objects.create_user(
            username="ada_solver",
            email="ada@example.com",
            first_name="Ada",
            last_name="Solver",
        )
        cls.group = Group.objects.create(name=STAFF_GROUP)
        cls.ctf = Ctf.objects.create(title="Spring CTF", slug="spring-ctf")
        cls.flag = Flag.objects.create(ctf=cls.ctf, title="First", flag="flag{x}", slug="first")
        cls.event = Event.objects.create(title="Sitz", slug="sitz", author=cls.member)
        cls.attendee = EventAttendees.objects.create(event=cls.event, user="Ada Solver", email="ada@example.com")

    def test_flag_solver_autocomplete_allowed_for_ctf_editor(self):
        self.client.force_login(self._editor(("ctf", "change_flag")))

        status, results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_functionary_member_autocomplete_allowed_for_functionary_editor(self):
        self.client.force_login(self._editor(("functionaries", "change_functionary")))

        status, results = self._results("functionaries", "functionary", "member")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_event_author_autocomplete_allowed_for_event_editor(self):
        self.client.force_login(self._editor(("events", "change_event")))

        status, results = self._results("events", "event", "author")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_invoice_participant_autocomplete_allowed_for_billing_editor(self):
        self.client.force_login(self._editor(("billing", "change_eventinvoice")))

        status, results = self._results("billing", "eventinvoice", "participant")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.attendee.pk)])

    def test_autocomplete_denied_without_related_or_referring_permission(self):
        self.client.force_login(self._editor(("news", "change_category")))

        status, _results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 403)

    def test_member_view_permission_still_grants_autocomplete(self):
        self.client.force_login(self._editor(("members", "view_member")))

        status, results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_superuser_autocomplete_unaffected(self):
        self.client.force_login(
            Member.objects.create_superuser(username="root", email="root@example.com", password="pass")
        )

        status, results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])


class InlineOnlyAutocompleteSite(AdminSite):
    """Admin site without standalone registration for the autocomplete source model."""

    def autocomplete_view(self, request):
        return ReferringObjectAutocompleteJsonView.as_view(admin_site=self)(request)


inline_only_site = InlineOnlyAutocompleteSite(name="inline_only_admin")


class GuessInline(django_admin.TabularInline):
    model = Guess
    autocomplete_fields = ("user",)


@django_admin.register(Ctf, site=inline_only_site)
class CtfInlineOnlyAdmin(django_admin.ModelAdmin):
    inlines = [FlagInline, GuessInline]


@django_admin.register(Member, site=inline_only_site)
class MemberSearchAdmin(django_admin.ModelAdmin):
    search_fields = ("username", "first_name", "last_name", "email")


@override_settings(STAFF_GROUPS=[STAFF_GROUP])
class InlineOnlyAutocompleteTests(_AutocompleteHelpersMixin, TestCase):
    """Access granted through an inline when the source model has no standalone admin.

    ``ReferringObjectAutocompleteJsonView`` falls back to checking the add/change
    permission on the *referring* object. When that object is only ever edited
    through an inline, the inline must grant access on its own.
    """

    @classmethod
    def setUpTestData(cls):
        cls.member = Member.objects.create_user(
            username="ada_inline",
            email="ada-inline@example.com",
            first_name="Ada",
            last_name="Inline",
        )
        cls.group = Group.objects.create(name=STAFF_GROUP)
        cls.ctf = Ctf.objects.create(title="Inline CTF", slug="inline-ctf")
        cls.flag = Flag.objects.create(ctf=cls.ctf, title="First", flag="flag{x}", slug="first")

    def _inline_results(self, user, app_label, model_name, field_name, term="ada"):
        request = RequestFactory().get(
            AUTOCOMPLETE_URL,
            {
                "app_label": app_label,
                "model_name": model_name,
                "field_name": field_name,
                "term": term,
            },
        )
        request.user = user
        try:
            response = inline_only_site.autocomplete_view(request)
        except PermissionDenied:
            return 403, []
        return 200, json.loads(response.content)["results"]

    def test_inline_add_permission_grants_autocomplete(self):
        user = self._editor(("ctf", "add_flag"))

        status, results = self._inline_results(user, "ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_inline_change_permission_grants_autocomplete(self):
        user = self._editor(("ctf", "change_flag"))

        status, results = self._inline_results(user, "ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_matching_inline_found_among_multiple_inlines(self):
        user = self._editor(("ctf", "add_guess"))

        status, results = self._inline_results(user, "ctf", "guess", "user")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.member.pk)])

    def test_inline_autocomplete_denied_without_inline_permission(self):
        user = self._editor(("news", "change_category"))

        status, _results = self._inline_results(user, "ctf", "flag", "solver")

        self.assertEqual(status, 403)


@override_settings(
    STAFF_GROUPS=[STAFF_GROUP],
    MEMBER_ADMIN_RESTRICTED_GROUP=RESTRICTED_GROUP,
    MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE=RESTRICTED_MEMBERSHIP_TYPE,
)
class RestrictedMemberAutocompleteTests(_AutocompleteHelpersMixin, TestCase):
    """The widened autocomplete still applies MemberAdmin row restrictions."""

    @classmethod
    def setUpTestData(cls):
        cls.allowed_type = MembershipType.objects.create(
            name=RESTRICTED_MEMBERSHIP_TYPE, permission_profile=ORDINARY_MEMBER
        )
        cls.other_type = MembershipType.objects.create(name="Ordinarie medlem", permission_profile=ORDINARY_MEMBER)
        cls.allowed_member = Member.objects.create_user(
            username="ada_allowed",
            email="ada-allowed@example.com",
            first_name="Ada",
            last_name="Allowed",
            membership_type=cls.allowed_type,
        )
        cls.other_member = Member.objects.create_user(
            username="ada_other",
            email="ada-other@example.com",
            first_name="Ada",
            last_name="Other",
            membership_type=cls.other_type,
        )
        cls.group = Group.objects.create(name=STAFF_GROUP)
        cls.restricted_group = Group.objects.create(name=RESTRICTED_GROUP)
        cls.ctf = Ctf.objects.create(title="Spring CTF", slug="spring-ctf")
        cls.flag = Flag.objects.create(ctf=cls.ctf, title="First", flag="flag{x}", slug="first")

    def _editor(self, *perms):
        user = super()._editor(*perms)
        user.groups.add(self.restricted_group)
        return user

    def test_restricted_editor_only_sees_allowed_membership_type(self):
        self.client.force_login(self._editor(("ctf", "change_flag")))

        status, results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in results], [str(self.allowed_member.pk)])

    def test_restricted_filter_does_not_apply_to_superuser(self):
        self.client.force_login(
            Member.objects.create_superuser(username="root", email="root@example.com", password="pass")
        )

        status, results = self._results("ctf", "flag", "solver")

        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(row["id"] for row in results), sorted([str(self.allowed_member.pk), str(self.other_member.pk)])
        )
