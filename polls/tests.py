from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.http import HttpResponse
from unittest.mock import patch

from django.utils import timezone

from members.models import (Member, MembershipType, ORDINARY_MEMBER,
                            Subscription, SubscriptionPayment)
from .models import Question, Choice
from . import views
from .vote import (ANYONE, MEMBERS_ONLY, ORDINARY_MEMBERS_ONLY,
                   VOTE_MEMBERS_ONLY, ERROR_MESSAGES, handle_selected_choices,
                   handle_vote, is_user_authorized_to_vote,
                   required_multiple_choices_matches_selected, validate_vote)


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
        request = self.factory.post(reverse("polls:vote", args=[self.question.id]), {"choice": [str(self.choice1.id), str(self.choice2.id), str(self.choice1.id)]})
        request.user = self.member
        response = views.vote(request, self.question.id)
        selected = mock_handle_vote.call_args.args[3]
        self.assertCountEqual(selected, [str(self.choice1.id), str(self.choice2.id)])
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
        self.member = Member.objects.create_user(username="validator", password="pwd", membership_type=self.membership_type)
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
        self.member = Member.objects.create_user(username="workflow", password="pwd", membership_type=self.membership_type)
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
