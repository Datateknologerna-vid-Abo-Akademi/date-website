import re
import unittest
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from members.models import NON_VOTING_MEMBER, ORDINARY_MEMBER, Member, MembershipType, Subscription, SubscriptionPayment

from . import admin as polls_admin
from . import views
from .models import Choice, Question, Vote
from .vote import (
    ANYONE,
    ERROR_MESSAGES,
    MEMBERS_ONLY,
    ORDINARY_MEMBERS_ONLY,
    VOTE_MEMBERS_ONLY,
    handle_selected_choices,
    handle_vote,
    is_user_authorized_to_vote,
    required_multiple_choices_matches_selected,
    validate_vote,
    voter_is_present,
)

# `attendance` is installed by DaTe alone, and `core.settings.test` inherits the
# date settings, so the poll-to-meeting tests below run here and are skipped on a
# settings module that does not install the app.
ATTENDANCE_INSTALLED = 'attendance' in settings.INSTALLED_APPS

if ATTENDANCE_INSTALLED:
    from attendance.models import AttendanceChange, AttendanceEvent, AttendancePoll

    ENTER = AttendanceChange.Type.ENTER
    LEAVE = AttendanceChange.Type.LEAVE

    def make_attendance_event(slug='mote', title='Möte'):
        """An attendance event that is open right now."""
        return AttendanceEvent.objects.create(title=title, slug=slug, start_datetime=timezone.now())

    def record_change(event, change_type, user):
        """Write one attendance change for a member."""
        return AttendanceChange.objects.create(event=event, user=user, type=change_type)


class QuestionModelTests(TestCase):
    def test_get_total_votes(self):
        question = Question.objects.create(question_text="Favourite colour?")
        Choice.objects.create(question=question, choice_text="red", votes=3)
        Choice.objects.create(question=question, choice_text="blue", votes=1)
        self.assertEqual(question.get_total_votes(), 4)

    def test_choice_vote_percentage(self):
        question = Question.objects.create(question_text="Favourite colour?")
        red = Choice.objects.create(question=question, choice_text="red", votes=3)
        blue = Choice.objects.create(question=question, choice_text="blue", votes=1)
        self.assertEqual(red.get_vote_percentage(), 75)
        self.assertEqual(blue.get_vote_percentage(), 25)


class VoteViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        membership = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(username="test", password="pwd", membership_type=membership)
        self.question = Question.objects.create(question_text="Favourite colour?")
        self.choice1 = Choice.objects.create(question=self.question, choice_text="red")
        self.choice2 = Choice.objects.create(question=self.question, choice_text="blue")

    @patch("polls.views.handle_vote")
    def test_vote_calls_handle_vote_authenticated(self, mock_handle_vote):
        mock_handle_vote.return_value = HttpResponse("ok")
        request = self.factory.post(
            reverse("polls:vote", args=[self.question.id]),
            {"choice": [str(self.choice1.id), str(self.choice2.id), str(self.choice1.id)]},
        )
        request.user = self.member
        response = views.vote(request, self.question.id)
        selected = mock_handle_vote.call_args.args[3]
        self.assertEqual(selected, [str(self.choice1.id), str(self.choice2.id), str(self.choice1.id)])
        self.assertEqual(response.content, b"ok")

    @patch("polls.views.handle_vote")
    def test_vote_calls_handle_vote_anonymous(self, mock_handle_vote):
        mock_handle_vote.return_value = HttpResponse("ok")
        request = self.factory.post(reverse("polls:vote", args=[self.question.id]), {"choice": [str(self.choice1.id)]})
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        response = views.vote(request, self.question.id)
        selected = mock_handle_vote.call_args.args[3]
        self.assertEqual(selected, [str(self.choice1.id)])
        self.assertEqual(response.content, b"ok")


class AuthorizationLogicTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(username="auth", password="pwd", membership_type=self.membership_type)
        self.question = Question.objects.create(question_text="Auth question")

    def test_anyone_allows_anonymous_users(self):
        self.question.voting_options = ANYONE
        self.question.save()
        self.assertTrue(is_user_authorized_to_vote(self.question, AnonymousUser()))

    def test_members_only_requires_authentication(self):
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()
        self.assertTrue(is_user_authorized_to_vote(self.question, self.member))
        self.assertFalse(is_user_authorized_to_vote(self.question, AnonymousUser()))

    def test_ordinary_members_only_checks_permission_profile(self):
        self.question.voting_options = ORDINARY_MEMBERS_ONLY
        self.question.save()
        non_member_type = MembershipType.objects.create(name="Other", permission_profile=0)
        other_member = Member.objects.create_user(username="other", password="pwd", membership_type=non_member_type)
        self.assertTrue(is_user_authorized_to_vote(self.question, self.member))
        self.assertFalse(is_user_authorized_to_vote(self.question, other_member))

    def test_non_voting_members_are_excluded_from_restricted_polls(self):
        non_voting_type = MembershipType.objects.create(name="Extra medlem", permission_profile=NON_VOTING_MEMBER)
        extra_member = Member.objects.create_user(username="extra", password="pwd", membership_type=non_voting_type)
        subscription = Subscription.objects.create(
            name="Annual",
            does_expire=True,
            renewal_scale='year',
            renewal_period=1,
            price=0,
        )
        SubscriptionPayment.objects.create(
            member=extra_member,
            subscription=subscription,
            date_paid=timezone.now().date(),
            date_expires=timezone.now().date() + timezone.timedelta(days=1),
        )

        self.question.voting_options = ORDINARY_MEMBERS_ONLY
        self.question.save()
        self.assertFalse(is_user_authorized_to_vote(self.question, extra_member))

        self.question.voting_options = VOTE_MEMBERS_ONLY
        self.question.save()
        self.assertFalse(is_user_authorized_to_vote(self.question, extra_member))

    def test_non_voting_members_can_vote_in_members_only_polls(self):
        non_voting_type = MembershipType.objects.create(name="Extra medlem", permission_profile=NON_VOTING_MEMBER)
        extra_member = Member.objects.create_user(username="extra", password="pwd", membership_type=non_voting_type)
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()
        self.assertTrue(is_user_authorized_to_vote(self.question, extra_member))

    def test_vote_members_only_requires_active_subscription(self):
        self.question.voting_options = VOTE_MEMBERS_ONLY
        self.question.save()
        self.assertFalse(is_user_authorized_to_vote(self.question, self.member))

        subscription = Subscription.objects.create(
            name="Annual",
            does_expire=True,
            renewal_scale='year',
            renewal_period=1,
            price=0,
        )
        SubscriptionPayment.objects.create(
            member=self.member,
            subscription=subscription,
            date_paid=timezone.now().date(),
            date_expires=timezone.now().date() + timezone.timedelta(days=1),
        )
        self.assertTrue(is_user_authorized_to_vote(self.question, self.member))


class RequiredChoicesTests(TestCase):
    def setUp(self):
        self.question = Question.objects.create(
            question_text="Multiple choice",
            multiple_choice=True,
            required_multiple_choices=2,
        )

    def test_requires_exact_number_when_set(self):
        self.assertFalse(required_multiple_choices_matches_selected(self.question, ['1']))
        self.assertTrue(required_multiple_choices_matches_selected(self.question, ['1', '2']))

    def test_returns_true_when_requirement_disabled(self):
        self.question.required_multiple_choices = None
        self.assertTrue(required_multiple_choices_matches_selected(self.question, []))


class ValidateVoteTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="validator", password="pwd", membership_type=self.membership_type
        )
        self.question = Question.objects.create(question_text="Validate me")
        self.choice = Choice.objects.create(question=self.question, choice_text="yes")

    def test_vote_ended_returns_error(self):
        self.question.end_vote = True
        self.question.save()
        message = validate_vote(None, self.question, self.member, [str(self.choice.id)])
        self.assertEqual(message, ERROR_MESSAGES['vote_ended'])

    def test_no_choice_returns_error(self):
        message = validate_vote(None, self.question, self.member, [])
        self.assertEqual(message, ERROR_MESSAGES['no_choice'])

    def test_single_choice_multiple_selected_error(self):
        other_choice = Choice.objects.create(question=self.question, choice_text="no")
        message = validate_vote(None, self.question, self.member, [str(self.choice.id), str(other_choice.id)])
        self.assertEqual(message, ERROR_MESSAGES['single_choice'])

    def test_not_authorized_returns_error(self):
        self.question.voting_options = MEMBERS_ONLY
        message = validate_vote(None, self.question, AnonymousUser(), [str(self.choice.id)])
        self.assertEqual(message, ERROR_MESSAGES['not_authorized'])

    def test_already_voted_blocks_non_anyone_questions(self):
        self.question.voting_options = MEMBERS_ONLY
        self.question.voters.add(self.member)
        message = validate_vote(None, self.question, self.member, [str(self.choice.id)])
        self.assertEqual(message, ERROR_MESSAGES['already_voted'])

    def test_anyone_allows_multiple_votes(self):
        self.question.voting_options = ANYONE
        self.question.voters.add(self.member)
        message = validate_vote(None, self.question, self.member, [str(self.choice.id)])
        self.assertIsNone(message)


class HandleVoteWorkflowTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="workflow", password="pwd", membership_type=self.membership_type
        )
        self.question = Question.objects.create(question_text="Workflow")
        self.choice = Choice.objects.create(question=self.question, choice_text="option")
        self.factory = RequestFactory()

    def test_handle_selected_choices_increments_votes_and_records_voter(self):
        handle_selected_choices(self.question, [self.choice.id], self.member)
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)
        self.assertIn(self.member, self.question.voters.all())

    def test_handle_vote_redirects_on_success(self):
        request = self.factory.post(reverse('polls:vote', args=[self.question.id]), {'choice': [str(self.choice.id)]})
        request.user = self.member
        response = handle_vote(request, self.question, self.member, [str(self.choice.id)])
        self.assertEqual(response.status_code, 302)

    def test_handle_vote_renders_error_template(self):
        request = self.factory.post(reverse('polls:vote', args=[self.question.id]), {})
        request.user = self.member
        response = handle_vote(request, self.question, self.member, [])
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Du valde inget alternativ', response.content)


class ForgedChoiceTests(TestCase):
    """A posted choice has to be an answer to the question being voted on.

    The ids come straight from the POST, so a crafted submission could name the
    choices of another poll and inflate that poll's counters. `validate_vote`
    refuses it, and `handle_selected_choices` is scoped to the question so the
    write path is safe even when the validation is bypassed.
    """

    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="forger", password="pwd", membership_type=self.membership_type
        )
        self.question = Question.objects.create(question_text="Frågan som röstas på")
        self.choice = Choice.objects.create(question=self.question, choice_text="ja")
        self.other_question = Question.objects.create(question_text="En annan fråga")
        self.other_choice = Choice.objects.create(question=self.other_question, choice_text="annat", votes=5)

    def test_a_choice_from_another_question_is_refused(self):
        message = validate_vote(None, self.question, self.member, [str(self.other_choice.id)])

        self.assertEqual(message, ERROR_MESSAGES['invalid_choice'])
        self.assertNotEqual(message, ERROR_MESSAGES['no_choice'])

    def test_a_choice_id_that_is_not_a_number_is_refused(self):
        message = validate_vote(None, self.question, self.member, ['inte-ett-id'])

        self.assertEqual(message, ERROR_MESSAGES['invalid_choice'])

    def test_a_forged_choice_changes_no_counter(self):
        """The write path on its own, with validate_vote() deliberately skipped."""
        handle_selected_choices(self.question, [self.other_choice.id], self.member)

        self.other_choice.refresh_from_db()
        self.choice.refresh_from_db()
        self.assertEqual(self.other_choice.votes, 5)
        self.assertEqual(self.choice.votes, 0)

    def test_a_forged_vote_is_refused_and_writes_nothing(self):
        """Through the view, where the refusal comes before anything is written."""
        response = self.client.post(
            reverse('polls:vote', args=[self.question.id]),
            {'choice': [str(self.other_choice.id)]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ERROR_MESSAGES['invalid_choice'])
        self.other_choice.refresh_from_db()
        self.assertEqual(self.other_choice.votes, 5)
        self.assertEqual(Vote.objects.count(), 0)

    def test_numeric_aliases_of_one_choice_do_not_satisfy_required_choices(self):
        self.question.multiple_choice = True
        self.question.required_multiple_choices = 2
        self.question.save(update_fields=['multiple_choice', 'required_multiple_choices'])
        other_choice = Choice.objects.create(question=self.question, choice_text="nej")
        self.client.force_login(self.member)

        response = self.client.post(
            reverse('polls:vote', args=[self.question.id]),
            {'choice': [str(self.choice.id), f"+{self.choice.id}"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ERROR_MESSAGES['invalid_choice'])
        self.choice.refresh_from_db()
        other_choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 0)
        self.assertEqual(other_choice.votes, 0)
        self.assertEqual(Vote.objects.count(), 0)

    def test_required_multiple_choice_post_counts_distinct_choices(self):
        self.question.multiple_choice = True
        self.question.required_multiple_choices = 2
        self.question.save(update_fields=['multiple_choice', 'required_multiple_choices'])
        other_choice = Choice.objects.create(question=self.question, choice_text="nej")
        self.client.force_login(self.member)

        response = self.client.post(
            reverse('polls:vote', args=[self.question.id]),
            {'choice': [str(self.choice.id), str(other_choice.id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.choice.refresh_from_db()
        other_choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)
        self.assertEqual(other_choice.votes, 1)
        self.assertEqual(Vote.objects.filter(question=self.question, user=self.member).count(), 1)

    def test_a_real_choice_still_counts(self):
        """The scoped update still updates the question's own choices."""
        handle_selected_choices(self.question, [self.choice.id], self.member)

        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)
        self.assertEqual(Vote.objects.count(), 1)


@unittest.skipUnless(ATTENDANCE_INSTALLED, "the attendance app is not installed in this settings module")
class VoterPresenceTests(TestCase):
    """The poll gate: only people in the meeting's room may vote on it."""

    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="narvarande", password="pwd", membership_type=self.membership_type
        )
        self.event = make_attendance_event()
        self.question = Question.objects.create(question_text="Mötesfråga")
        self.choice = Choice.objects.create(question=self.question, choice_text="ja")
        self.attachment = AttendancePoll.objects.create(question=self.question, event=self.event)

    def test_a_present_member_may_vote(self):
        record_change(self.event, ENTER, self.member)

        self.assertTrue(voter_is_present(self.question, self.member))
        self.assertIsNone(validate_vote(None, self.question, self.member, [str(self.choice.id)]))

    def test_a_member_who_has_not_arrived_is_refused(self):
        self.assertFalse(voter_is_present(self.question, self.member))
        self.assertEqual(
            validate_vote(None, self.question, self.member, [str(self.choice.id)]),
            ERROR_MESSAGES['not_present'],
        )

    def test_a_member_who_left_before_voting_is_refused(self):
        record_change(self.event, ENTER, self.member)
        record_change(self.event, LEAVE, self.member)

        self.assertFalse(voter_is_present(self.question, self.member))
        self.assertEqual(
            validate_vote(None, self.question, self.member, [str(self.choice.id)]),
            ERROR_MESSAGES['not_present'],
        )

    def test_presence_at_another_meeting_is_not_presence_here(self):
        record_change(make_attendance_event(slug="annat", title="Annat möte"), ENTER, self.member)

        self.assertFalse(voter_is_present(self.question, self.member))
        self.assertEqual(
            validate_vote(None, self.question, self.member, [str(self.choice.id)]),
            ERROR_MESSAGES['not_present'],
        )

    def test_an_anonymous_voter_is_refused(self):
        """The poll is open to anyone, and the gate still refuses an anonymous visitor."""
        self.assertEqual(self.question.voting_options, ANYONE)

        self.assertFalse(voter_is_present(self.question, AnonymousUser()))
        self.assertEqual(
            validate_vote(None, self.question, AnonymousUser(), [str(self.choice.id)]),
            ERROR_MESSAGES['not_present'],
        )

    def test_the_attachment_is_read_through_the_reverse_accessor(self):
        self.assertEqual(self.question.attendance_poll, self.attachment)
        self.assertEqual(self.event.polls.get(), self.attachment)

    def test_a_poll_without_an_attachment_is_unaffected(self):
        """The regression that matters most: an ordinary poll keeps its old rules."""
        unattached = Question.objects.create(question_text="Vanlig fråga")
        choice = Choice.objects.create(question=unattached, choice_text="ja")

        self.assertTrue(voter_is_present(unattached, AnonymousUser()))
        self.assertTrue(voter_is_present(unattached, self.member))
        self.assertIsNone(validate_vote(None, unattached, AnonymousUser(), [str(choice.id)]))

    def test_the_helper_allows_everyone_when_attendance_is_not_installed(self):
        """The other six associations have no attendance app to consult."""
        # The refusal below is what the patch is measured against.
        self.assertFalse(voter_is_present(self.question, self.member))

        with patch('polls.vote.apps.is_installed', return_value=False):
            self.assertTrue(voter_is_present(self.question, self.member))
            self.assertTrue(voter_is_present(self.question, AnonymousUser()))

    def test_the_eligibility_message_wins_over_the_presence_message(self):
        """The gate is checked after authorization, so an ineligible voter hears that."""
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()

        self.assertFalse(voter_is_present(self.question, AnonymousUser()))
        self.assertEqual(
            validate_vote(None, self.question, AnonymousUser(), [str(self.choice.id)]),
            ERROR_MESSAGES['not_authorized'],
        )

    def test_a_member_who_already_voted_hears_that_before_the_room_check(self):
        """The existing checks keep their position, so the gate cannot mask them."""
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()
        self.question.voters.add(self.member)

        # Present or not, this member has voted on this poll already.
        self.assertFalse(voter_is_present(self.question, self.member))
        self.assertEqual(
            validate_vote(None, self.question, self.member, [str(self.choice.id)]),
            ERROR_MESSAGES['already_voted'],
        )

    def test_a_vote_from_the_room_is_redirected(self):
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()
        record_change(self.event, ENTER, self.member)
        self.client.force_login(self.member)

        response = self.client.post(reverse('polls:vote', args=[self.question.id]), {'choice': [str(self.choice.id)]})

        self.assertEqual(response.status_code, 302)
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)

    def test_a_vote_from_outside_the_room_renders_the_message(self):
        self.question.voting_options = MEMBERS_ONLY
        self.question.save()
        self.client.force_login(self.member)

        response = self.client.post(reverse('polls:vote', args=[self.question.id]), {'choice': [str(self.choice.id)]})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ERROR_MESSAGES['not_present'])
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 0)
        self.assertEqual(Vote.objects.count(), 0)


@unittest.skipUnless(ATTENDANCE_INSTALLED, "the attendance app is not installed in this settings module")
class PollPageAttendancePromptTests(TestCase):
    """The poll page's half of the flow: it tells a room-only voter where to check in."""

    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="roestare", password="pwd", membership_type=self.membership_type
        )
        self.event = make_attendance_event(slug="arsmote", title="Årsmöte")
        self.question = Question.objects.create(question_text="Mötesfråga", voting_options=MEMBERS_ONLY)
        self.choice = Choice.objects.create(question=self.question, choice_text="ja")
        AttendancePoll.objects.create(question=self.question, event=self.event)
        self.page_url = reverse('polls:detail', args=[self.question.id])
        self.vote_url = reverse('polls:vote', args=[self.question.id])
        self.check_in_url = reverse('attendance-event-view', args=[self.event.slug])

    def test_a_member_who_is_not_present_is_sent_to_the_check_in_page(self):
        self.client.force_login(self.member)

        response = self.client.get(self.page_url)

        self.assertContains(response, "Årsmöte")
        self.assertContains(response, "Ange koden och checka in")
        # The round trip: the check-in page sends the voter back to this page.
        self.assertContains(response, f'href="{self.check_in_url}?next={self.page_url}"')

    def test_a_refused_vote_still_returns_the_voter_to_this_page(self):
        """The link names the poll page, not the endpoint that rendered the refusal.

        A refusal is rendered by the vote view, so ``request.path`` there ends in
        ``/vote/``: a link built from it would send a voter who tried to vote
        first, and only then went to check in, to the vote endpoint, where the
        page renders again with a spurious "you picked nothing" message.
        """
        self.client.force_login(self.member)

        response = self.client.post(self.vote_url, {"choice": [self.choice.id]})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Du måste vara närvarande")
        self.assertContains(response, f'href="{self.check_in_url}?next={self.page_url}"')
        self.assertNotContains(response, f"next={self.vote_url}")

    def test_a_present_member_reads_that_they_are_in_the_room(self):
        record_change(self.event, ENTER, self.member)
        self.client.force_login(self.member)

        response = self.client.get(self.page_url)

        self.assertContains(response, "Du är närvarande på Årsmöte.")
        self.assertNotContains(response, self.check_in_url)
        self.assertNotContains(response, "Ange koden och checka in")

    def test_an_anonymous_visitor_is_sent_to_the_login_page(self):
        """A guest cannot vote by checking in, so the poll sends them to sign in."""
        response = self.client.get(self.page_url)

        self.assertContains(response, f'href="{reverse("members:login")}?next={self.page_url}"')
        self.assertNotContains(response, self.check_in_url)
        self.assertNotContains(response, "Ange koden och checka in")

    def test_an_ordinary_poll_shows_none_of_the_prompt(self):
        ordinary = Question.objects.create(question_text="Vanlig fråga")
        Choice.objects.create(question=ordinary, choice_text="ja")
        self.client.force_login(self.member)

        response = self.client.get(reverse('polls:detail', args=[ordinary.id]))

        self.assertIsNone(response.context['attendance_requirement'])
        self.assertNotContains(response, "Årsmöte")
        self.assertNotContains(response, self.check_in_url)
        self.assertNotContains(response, "Ange koden och checka in")
        self.assertNotContains(response, "Du är närvarande på")
        self.assertNotContains(response, "Röstningen kräver")
        self.assertNotContains(response, "/attendance/")

    def test_nothing_new_is_rendered_when_attendance_is_not_installed(self):
        """The other six associations have no check-in page to link to."""
        self.client.force_login(self.member)

        with patch('polls.vote.apps.is_installed', return_value=False):
            response = self.client.get(self.page_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['attendance_requirement'])
        self.assertNotContains(response, "Ange koden och checka in")
        self.assertNotContains(response, "Röstningen kräver")
        self.assertNotContains(response, "Årsmöte")
        # The check-in URL is not even resolved, so a site without the route is safe.
        self.assertNotContains(response, "/attendance/")

    def test_the_refusal_still_offers_the_check_in_page(self):
        """A voter who presses "Rösta" without checking in is not left at a dead end."""
        self.client.force_login(self.member)

        response = self.client.post(self.vote_url, {'choice': [str(self.choice.id)]})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ERROR_MESSAGES['not_present'])
        self.assertContains(response, "Ange koden och checka in")

    def test_the_page_and_the_vote_gate_agree_about_the_room(self):
        """The one test that fails if the page and voter_is_present() ever disagree.

        The page is read for what it renders, not for its context, so a prompt that
        claims presence it does not have is caught here as well.
        """
        for present in (False, True):
            with self.subTest(present=present):
                if present:
                    record_change(self.event, ENTER, self.member)
                self.client.force_login(self.member)

                page = self.client.get(self.page_url)
                page_says_present = "Du är närvarande på" in page.content.decode()
                requirement = page.context['attendance_requirement']

                # The object the page renders from and the gate the POST runs are
                # the same answer, and the rendered page carries that answer.
                self.assertEqual(requirement.is_present, voter_is_present(self.question, self.member))
                self.assertEqual(page_says_present, voter_is_present(self.question, self.member))
                self.assertEqual(requirement.event, self.event)

                vote = self.client.post(self.vote_url, {'choice': [str(self.choice.id)]})
                if page_says_present:
                    self.assertEqual(vote.status_code, 302)
                else:
                    self.assertContains(vote, ERROR_MESSAGES['not_present'])


@unittest.skipUnless(ATTENDANCE_INSTALLED, "the attendance app is not installed in this settings module")
class QuestionAdminAttendanceTests(TestCase):
    """The meeting column and the inline, on the poll page an editor works from."""

    def setUp(self):
        self.admin_user = Member.objects.create_user(
            username="admin",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
            is_superuser=True,
        )
        self.event = make_attendance_event(title="Årsmöte")
        self.question = Question.objects.create(question_text="Kopplad fråga")
        self.unattached = Question.objects.create(question_text="Vanlig fråga")
        self.changelist_url = reverse("admin:polls_question_changelist")

    def test_the_meeting_column_exists_only_with_the_attendance_app(self):
        with_app = polls_admin.question_list_display(True)
        without_app = polls_admin.question_list_display(False)

        self.assertIn('attendance_event', with_app)
        self.assertNotIn('attendance_event', without_app)
        # The column is an addition, so no variant loses a column it has today.
        self.assertEqual(set(without_app) - set(with_app), set())
        self.assertEqual(set(with_app) - set(without_app), {'attendance_event'})

    def test_the_registered_admin_uses_the_column_list_for_this_settings_module(self):
        """The class config is the one this settings module's flag asks for."""
        self.assertTrue(polls_admin.ATTENDANCE_INSTALLED)
        registered = admin.site._registry[Question]

        self.assertEqual(registered.list_display, polls_admin.question_list_display(True))
        # The column's relation is joined into the changelist query, not fetched
        # one row at a time. The query count below pins the effect.
        self.assertTrue(registered.get_queryset(None).query.select_related)

    def test_the_column_shows_the_meeting_or_a_dash(self):
        registered = admin.site._registry[Question]
        AttendancePoll.objects.create(question=self.question, event=self.event)

        self.assertEqual(registered.attendance_event(self.question), self.event)
        self.assertEqual(registered.attendance_event(self.unattached), '-')

    def test_the_changelist_renders_the_meeting(self):
        AttendancePoll.objects.create(question=self.question, event=self.event)
        self.client.force_login(self.admin_user)

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.event))
        self.assertContains(response, self.unattached.question_text)

    def test_the_meeting_column_costs_no_query_per_row(self):
        self.client.force_login(self.admin_user)
        AttendancePoll.objects.create(question=self.question, event=self.event)

        with CaptureQueriesContext(connection) as small:
            self.client.get(self.changelist_url)

        for index in range(5):
            question = Question.objects.create(question_text=f"Kopplad fråga {index}")
            AttendancePoll.objects.create(question=question, event=self.event)

        with CaptureQueriesContext(connection) as grown:
            self.client.get(self.changelist_url)

        self.assertEqual(len(small.captured_queries), len(grown.captured_queries))

    def test_the_inline_is_configured_for_one_meeting(self):
        """One poll, one meeting, and a Swedish heading for the section."""
        inline = polls_admin.AttendancePollInline

        self.assertEqual(str(inline.verbose_name_plural), 'Närvarokrav')
        self.assertEqual(inline.extra, 0)
        self.assertEqual(inline.max_num, 1)

    def test_the_poll_page_offers_the_meeting_on_the_poll_being_edited(self):
        """The inline's parent is the poll, so Django fills that side in."""
        AttendancePoll.objects.create(question=self.question, event=self.event)
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_change", args=[self.question.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Närvarokrav')
        self.assertContains(response, 'name="attendance_poll-0-event"')
        self.assertContains(response, str(self.event))

    def test_the_add_page_offers_the_inline_before_the_poll_exists(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Närvarokrav')

    def test_the_poll_page_offers_the_inline_on_a_poll_without_a_meeting(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_change", args=[self.unattached.pk]))

        self.assertEqual(response.status_code, 200)
        # The inline is there for the editor to attach a meeting to this poll.
        self.assertContains(response, 'Närvarokrav')

    def test_question_editors_can_render_the_inline_without_attendance_permissions(self):
        editor = Member.objects.create_user(
            username="poll-editor",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        editor.groups.add(Group.objects.create(name=settings.STAFF_GROUPS[0]))
        editor.user_permissions.add(
            Permission.objects.get(content_type__app_label="polls", codename="add_question"),
            Permission.objects.get(content_type__app_label="polls", codename="change_question"),
        )
        self.assertFalse(editor.has_perm("attendance.add_attendancepoll"))
        self.assertFalse(editor.has_perm("attendance.change_attendancepoll"))
        AttendancePoll.objects.create(question=self.question, event=self.event)
        self.client.force_login(editor)

        response = self.client.get(reverse("admin:polls_question_change", args=[self.question.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="attendance_poll-0-event"')
        self.assertContains(response, str(self.event))

    def test_the_poll_page_reads_the_room_and_the_turnout(self):
        """Both numbers are on the change page, and they are different numbers.

        Two people in the room and one vote behind the poll is the case the
        readout exists for: the person running the vote compares the two before
        deciding whether to wait any longer.
        """
        AttendancePoll.objects.create(question=self.question, event=self.event)
        other_member = Member.objects.create_user(
            username="narvarande2",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        record_change(self.event, ENTER, self.admin_user)
        record_change(self.event, ENTER, other_member)
        self.question.voters.add(self.admin_user)
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_change", args=[self.question.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Närvarande i mötet nu')
        self.assertContains(response, 'Har röstat')
        # Which fields the admin decided to show, and what the reader sees. The
        # names are theme-independent; the rendered numbers are read after the
        # markup is stripped, because the classic admin and Unfold wrap a read-only
        # field differently and the shape of that wrapper is not what matters here.
        readonly = response.context['adminform'].readonly_fields
        self.assertIn('attendance_present_now', readonly)
        self.assertIn('attendance_voters', readonly)
        rendered = ' '.join(re.sub(r'<[^>]+>', ' ', response.content.decode()).split())
        self.assertRegex(rendered, r'Närvarande i mötet nu:?\s*2\b')
        self.assertRegex(rendered, r'Har röstat:?\s*1\b')

    def test_the_readout_follows_the_room_rather_than_a_stored_value(self):
        """The headcount is answered when the page is read, from the change log."""
        AttendancePoll.objects.create(question=self.question, event=self.event)
        registered = admin.site._registry[Question]
        record_change(self.event, ENTER, self.admin_user)

        self.assertEqual(registered.attendance_present_now(self.question), 1)

        record_change(self.event, LEAVE, self.admin_user)

        self.assertEqual(registered.attendance_present_now(self.question), 0)

    def test_the_readout_counts_the_votes_that_have_been_cast(self):
        AttendancePoll.objects.create(question=self.question, event=self.event)
        registered = admin.site._registry[Question]

        self.assertEqual(registered.attendance_voters(self.question), 0)

        self.question.voters.add(self.admin_user)

        self.assertEqual(registered.attendance_voters(self.question), 1)

    def test_the_readout_is_absent_for_a_poll_without_a_meeting(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_change", args=[self.unattached.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Närvarande i mötet nu')
        self.assertNotContains(response, 'Har röstat')
        self.assertNotContains(response, 'field-attendance_present_now')

    def test_the_readout_is_absent_before_the_poll_exists(self):
        """The add page has no attachment to read yet, so it renders as before."""
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:polls_question_add"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Närvarande i mötet nu')
        self.assertNotContains(response, 'Har röstat')

    def test_the_readout_is_not_a_changelist_column(self):
        """A readout meant for one poll must not add a query per changelist row."""
        registered = admin.site._registry[Question]

        self.assertNotIn('attendance_present_now', registered.list_display)
        self.assertNotIn('attendance_voters', registered.list_display)

    def test_the_readout_fields_are_added_only_for_an_attached_poll(self):
        """The attachment is the switch, so no page needs a fieldset of its own."""
        registered = admin.site._registry[Question]
        AttendancePoll.objects.create(question=self.question, event=self.event)

        self.assertEqual(registered.get_readonly_fields(None, self.unattached), ())
        self.assertEqual(
            registered.get_readonly_fields(None, self.question),
            ('attendance_present_now', 'attendance_voters'),
        )
