from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from members.models import Member, MembershipType, ORDINARY_MEMBER
from .models import Choice, MEMBERS_ONLY, Question
from . import views


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
        request = self.factory.post(
            reverse("polls:vote", args=[self.question.id]), {"choice": [str(self.choice1.id)]}
        )
        request.user = AnonymousUser()
        response = views.vote(request, self.question.id)
        selected = mock_handle_vote.call_args.args[3]
        self.assertEqual(selected, [str(self.choice1.id)])
        self.assertEqual(response.content, b"ok")


class DetailViewTests(TestCase):
    def setUp(self):
        membership = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="voter", password="pwd", membership_type=membership
        )
        self.question = Question.objects.create(
            question_text="Best colour?", voting_options=MEMBERS_ONLY
        )
        self.question.voters.add(self.member)

    def test_detail_shows_already_voted_message(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("polls:detail", args=[self.question.id]))
        self.assertContains(response, "Du har redan röstat.")
        self.assertNotContains(response, "<form")
