import json
import time
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from members.gdpr import collect_personal_data
from members.models import ORDINARY_MEMBER, Member, MembershipType


class GDRPTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='gdpruser',
            email='gdpr@example.com',
            first_name='Test',
            last_name='User',
            phone='0401234567',
            address='Testgatan 1',
            zip_code='20500',
            city='Åbo',
            country='Finland',
        )
        cls.other_member = Member.objects.create_user(
            username='otheruser',
            email='other@example.com',
            first_name='Other',
            last_name='User',
        )

    def setUp(self):
        self.member.refresh_from_db()


class GDPRExportTests(GDRPTestBase):
    def test_export_returns_member_profile(self):
        data = collect_personal_data('gdpr@example.com')
        self.assertEqual(len(data['members']), 1)
        profile = data['members'][0]
        self.assertEqual(profile['username'], 'gdpruser')
        self.assertEqual(profile['email'], 'gdpr@example.com')
        self.assertEqual(profile['first_name'], 'Test')
        self.assertEqual(profile['phone'], '0401234567')

    def test_export_is_case_insensitive_and_does_not_match_others(self):
        data = collect_personal_data('GDPR@Example.COM')
        self.assertEqual(len(data['members']), 1)
        data = collect_personal_data('other@example.com')
        self.assertEqual(data['members'][0]['username'], 'otheruser')

    def test_export_includes_event_attendee_and_invoice(self):
        from billing.models import EventInvoice
        from events.models import Event, EventAttendees

        event = Event.objects.create(
            title='GDPR Test Event',
            slug='gdpr-test-event',
            author=self.other_member,
        )
        attendee = EventAttendees.objects.create(
            event=event,
            user='Test User',
            email='gdpr@example.com',
            preferences={'drink': 'coffee'},
        )
        EventInvoice.objects.create(
            participant=attendee,
            invoice_number=12345,
            reference_number='24000000123456',
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            amount=10,
            currency='EUR',
        )

        data = collect_personal_data('gdpr@example.com')
        self.assertEqual(len(data['event_attendees']), 1)
        self.assertEqual(data['event_attendees'][0]['preferences'], {'drink': 'coffee'})
        self.assertEqual(len(data['billing_invoices']), 1)
        self.assertEqual(data['billing_invoices'][0]['invoice_number'], 12345)

    def test_export_command_outputs_json(self):
        out = StringIO()
        call_command('gdpr_export', 'gdpr@example.com', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(data['query_email'], 'gdpr@example.com')
        self.assertEqual(len(data['members']), 1)


class GDPRDeleteTests(GDRPTestBase):
    def test_dry_run_makes_no_changes(self):
        from events.models import Event, EventAttendees

        event = Event.objects.create(
            title='GDPR Event',
            slug='gdpr-event',
            author=self.other_member,
        )
        EventAttendees.objects.create(
            event=event,
            user='Test User',
            email='gdpr@example.com',
            preferences={'drink': 'coffee'},
        )

        call_command('gdpr_delete', 'gdpr@example.com', dry_run=True)
        self.member.refresh_from_db()
        self.assertEqual(self.member.username, 'gdpruser')
        self.assertEqual(self.member.email, 'gdpr@example.com')
        attendee = EventAttendees.objects.get(event=event)
        self.assertEqual(attendee.user, 'Test User')
        self.assertEqual(attendee.email, 'gdpr@example.com')

    def test_delete_anonymizes_member_and_attendee(self):
        from events.models import Event, EventAttendees

        event = Event.objects.create(
            title='GDPR Event',
            slug='gdpr-event-2',
            author=self.other_member,
        )
        EventAttendees.objects.create(
            event=event,
            user='Test User',
            email='gdpr@example.com',
            preferences={'drink': 'coffee'},
        )
        TOTPDevice.objects.create(user=self.member, name='test', confirmed=True)

        call_command('gdpr_delete', 'gdpr@example.com')
        self.member.refresh_from_db()
        self.assertIsNone(self.member.email)
        self.assertFalse(self.member.is_active)
        self.assertFalse(self.member.has_usable_password())
        self.assertEqual(self.member.first_name, '')
        self.assertNotEqual(self.member.username, 'gdpruser')

        attendee = EventAttendees.objects.get(event=event)
        self.assertEqual(attendee.user, 'Anonym')
        self.assertIsNone(attendee.email)
        self.assertEqual(attendee.preferences, {})
        self.assertTrue(attendee.anonymous)

        self.assertFalse(TOTPDevice.objects.filter(user=self.member).exists())

    def test_delete_keeps_votes_and_authored_content(self):
        from news.models import Category, Post
        from polls.models import Choice, Question

        post = Post.objects.create(
            title='Authored post',
            slug='authored-post',
            content='content',
            author=self.member,
        )
        question = Question.objects.create(question_text='Test question')
        Choice.objects.create(question=question, choice_text='Yes')
        question.voters.add(self.member)

        call_command('gdpr_delete', 'gdpr@example.com')
        self.member.refresh_from_db()
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.assertTrue(question.voters.filter(pk=self.member.pk).exists())

    def test_delete_deletes_guesses_and_alumni_tokens(self):
        import uuid

        from alumni.models import AlumniUpdateToken
        from ctf.models import Ctf, Flag, Guess

        ctf = Ctf.objects.create(title='GDPR CTF', slug='gdpr-ctf', content='content')
        flag = Flag.objects.create(ctf=ctf, title='flag1', flag='flag{1}', slug='flag-1')
        Guess.objects.create(ctf=ctf, user=self.member, flag=flag, guess='wrong')
        AlumniUpdateToken.objects.create(
            email='gdpr@example.com',
            token=uuid.uuid4(),
        )

        call_command('gdpr_delete', 'gdpr@example.com')
        self.assertFalse(Guess.objects.filter(user=self.member).exists())
        self.assertFalse(AlumniUpdateToken.objects.filter(email='gdpr@example.com').exists())

    def test_delete_anonymizes_harassment_email_keeps_message(self):
        from harassment.models import Harassment

        report = Harassment.objects.create(
            email='gdpr@example.com',
            message='Incident description that must be kept',
        )

        call_command('gdpr_delete', 'gdpr@example.com')
        report.refresh_from_db()
        self.assertIsNone(report.email)
        self.assertEqual(report.message, 'Incident description that must be kept')

    def test_delete_without_member_still_handles_attendees(self):
        from events.models import Event, EventAttendees

        event = Event.objects.create(
            title='GDPR Event',
            slug='gdpr-event-3',
            author=self.other_member,
        )
        EventAttendees.objects.create(
            event=event,
            user='No Account User',
            email='noaccount@example.com',
        )

        call_command('gdpr_delete', 'noaccount@example.com')
        attendee = EventAttendees.objects.get(event=event)
        self.assertEqual(attendee.user, 'Anonym')
        self.assertIsNone(attendee.email)
