"""Regression tests for admin pages that used to scale with row count.

The admin is operated by non-developers, so these tests pin the query shape
of the slowest pages rather than exact query counts: the page must not issue
one query (or one full option list) per related row.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventAttendees
from functionaries.models import Functionary, FunctionaryRole
from members.models import ORDINARY_MEMBER, Member, MembershipType
from polls.models import Choice, Question, Vote
from staticpages.models import StaticPageNav, StaticUrl

RUN_ID = uuid.uuid4().hex[:6]


class AdminPerformanceTestCase(TestCase):
    def setUp(self):
        self.admin_user = Member.objects.create_superuser(
            username=f"perf-admin-{RUN_ID}",
            password="pass",
            email=f"perf-admin-{RUN_ID}@example.com",
        )
        self.client.force_login(self.admin_user)


class EventAttendeeInlineTests(AdminPerformanceTestCase):
    def setUp(self):
        super().setUp()
        self.event = Event.objects.create(
            title="Performance event",
            slug=f"performance-event-{RUN_ID}",
            author=self.admin_user,
            sign_up=True,
            sign_up_avec=True,
        )
        self.change_url = reverse("admin:events_event_change", args=[self.event.pk])

    def _attendees(self, count):
        EventAttendees.objects.bulk_create(
            [
                EventAttendees(
                    event=self.event,
                    attendee_nr=(index + 1) * 10,
                    user=f"Perf Person {index}",
                    email=f"perf-{RUN_ID}-{index}@example.com",
                    time_registered=timezone.now(),
                )
                for index in range(count)
            ]
        )

    def test_avec_autocomplete_is_scoped_to_the_edited_event(self):
        self._attendees(25)
        other_event = Event.objects.create(
            title="Other event",
            slug=f"other-event-{RUN_ID}",
            author=self.admin_user,
        )
        other = EventAttendees.objects.create(
            event=other_event,
            user="Other Person",
            email="other@example.com",
            time_registered=timezone.now(),
        )
        event_ids = set(EventAttendees.objects.filter(event=self.event).values_list("pk", flat=True))

        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "events",
                "model_name": "eventattendees",
                "field_name": "avec_for",
                "event_id": self.event.pk,
                "term": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        ids = {int(row["id"]) for row in response.json()["results"]}
        self.assertTrue(ids)
        self.assertNotIn(other.pk, ids)
        self.assertTrue(ids.issubset(event_ids))

    def test_change_form_renders_an_autocomplete_not_an_option_per_attendee(self):
        self._attendees(40)

        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"event_id={self.event.pk}")
        self.assertLess(response.content.count(b"<option"), 100)

    def test_change_form_queries_do_not_grow_per_attendee(self):
        with CaptureQueriesContext(connection) as empty:
            self.client.get(self.change_url)

        self._attendees(40)

        with CaptureQueriesContext(connection) as full:
            self.client.get(self.change_url)

        self.assertLessEqual(len(full.captured_queries) - len(empty.captured_queries), 5)


class MemberAdminPerformanceTests(AdminPerformanceTestCase):
    def setUp(self):
        super().setUp()
        self.membership_type = MembershipType.objects.create(
            name=f"Ordinary {RUN_ID}",
            permission_profile=ORDINARY_MEMBER,
        )
        for index in range(60):
            Member.objects.create_user(
                username=f"pm-{RUN_ID}-{index}",
                password="pass",
                email=f"pm-{RUN_ID}-{index}@example.com",
                membership_type=self.membership_type,
            )

    def test_member_changelist_does_not_query_per_row(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("admin:members_member_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries.captured_queries), 60)

    def test_staff_flag_comes_from_the_changelist_annotation(self):
        group, _ = Group.objects.get_or_create(name=settings.STAFF_GROUPS[0])
        member = Member.objects.get(username=f"pm-{RUN_ID}-0")
        member.groups.add(group)
        request = RequestFactory().get("/admin/members/member/")
        request.user = self.admin_user
        model_admin = admin.site._registry[Member]

        annotated = model_admin.get_queryset(request).get(pk=member.pk)

        self.assertTrue(annotated._is_staff)
        self.assertTrue(model_admin.is_staff(annotated))

    def test_superuser_staff_check_does_not_query_groups(self):
        with self.assertNumQueries(0):
            self.assertTrue(self.admin_user.is_staff)


class PollInlinePerformanceTests(AdminPerformanceTestCase):
    def setUp(self):
        super().setUp()
        self.membership_type = MembershipType.objects.create(
            name=f"Ordinary {RUN_ID}",
            permission_profile=ORDINARY_MEMBER,
        )
        self.question = Question.objects.create(
            question_text="Performance question",
            show_results=True,
        )
        self.change_url = reverse("admin:polls_question_change", args=[self.question.pk])
        Choice.objects.bulk_create(
            [Choice(question=self.question, choice_text=f"Choice {index}", votes=1) for index in range(5)]
        )

    def test_vote_inline_does_not_query_per_vote(self):
        with CaptureQueriesContext(connection) as empty:
            self.client.get(self.change_url)

        voters = [
            Member.objects.create_user(
                username=f"pv-{RUN_ID}-{index}",
                password="pass",
                email=f"pv-{RUN_ID}-{index}@example.com",
                membership_type=self.membership_type,
            )
            for index in range(20)
        ]
        Vote.objects.bulk_create([Vote(question=self.question, user=voter) for voter in voters])

        with CaptureQueriesContext(connection) as full:
            response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(full.captured_queries) - len(empty.captured_queries), 5)


class EagerCountTests(AdminPerformanceTestCase):
    def test_staticpage_nav_link_count_uses_the_annotation(self):
        nav = StaticPageNav.objects.create(category_name="Performance")
        StaticUrl.objects.create(title="One", url="/one/", category=nav)
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        model_admin = admin.site._registry[StaticPageNav]

        annotated = model_admin.get_queryset(request).get(pk=nav.pk)

        with self.assertNumQueries(0):
            self.assertEqual(model_admin.link_count(annotated), 1)

    def test_functionary_count_uses_the_annotation(self):
        role = FunctionaryRole.objects.create(title="Performance role")
        Functionary.objects.create(functionary_role=role, name="Perf Person", year=2026)
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        model_admin = admin.site._registry[FunctionaryRole]

        annotated = model_admin.get_queryset(request).get(pk=role.pk)

        with self.assertNumQueries(0):
            self.assertIn("1", str(model_admin.functionary_count(annotated)))


class AdminWhiteScreenTests(AdminPerformanceTestCase):
    def test_admin_base_reveals_content_when_alpine_is_late(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        js_path = Path(settings.BASE_DIR) / "date/static/date/js/admin_sidebar.js"
        self.assertIn("removeAttribute('x-cloak')", js_path.read_text(encoding="utf-8"))
        if settings.USE_UNFOLD:
            self.assertContains(response, "date/js/admin_sidebar.js")
        else:
            self.assertContains(response, "removeAttribute('x-cloak')")
            self.assertContains(response, 'data-cfasync="false"')


class AdminPermissionCacheTests(AdminPerformanceTestCase):
    def test_permission_check_queries_once_per_request(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        # Real requests pass through django_otp.middleware.OTPMiddleware,
        # which adds is_verified(). RequestFactory does not run middleware.
        request.user.is_verified = lambda: False
        site = admin.site

        with CaptureQueriesContext(connection):
            self.assertTrue(site.has_permission(request))

        with CaptureQueriesContext(connection) as second:
            self.assertTrue(site.has_permission(request))

        self.assertEqual(len(second.captured_queries), 0)
