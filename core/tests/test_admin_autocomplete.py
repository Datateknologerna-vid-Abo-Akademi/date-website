"""Autocomplete access for editors of the object that owns the related field.

Django's ``AutocompleteJsonView`` only answers when the user holds view
permission on the *related* model. Several admins here point at
``members.Member`` (and ``events.EventAttendees``) through ``autocomplete_fields``
while their editors are deliberately not trusted with the full member registry,
which left those dropdowns empty. ``core.admin.ReferringObjectAutocompleteJsonView``
also accepts the request when the user may add/change the referring object.
"""

import json

from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ctf.models import Ctf, Flag
from events.models import Event, EventAttendees
from members.models import Member

AUTOCOMPLETE_URL = reverse("admin:autocomplete")
STAFF_GROUP = "content-editors"


@override_settings(STAFF_GROUPS=[STAFF_GROUP])
class ReferringObjectAutocompleteTests(TestCase):
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
