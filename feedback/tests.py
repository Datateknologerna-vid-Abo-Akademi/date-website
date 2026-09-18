from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from feedback.admin import FeedbackFormSettingsAdmin, FeedbackSubmissionAdmin
from feedback.models import FeedbackEmailRecipient, FeedbackFormSettings, FeedbackSubmission


class FeedbackFormViewTests(TestCase):
    """/forms/ is a standalone feedback form, separate from the harassment
    report form at /social/harassment/ - see feedback/views.py and
    docs/dev/feedback.md."""

    def test_page_renders(self):
        response = self.client.get(reverse('feedback:form'))
        self.assertEqual(response.status_code, 200)

    def test_page_shows_default_intro_text(self):
        response = self.client.get(reverse('feedback:form'))
        self.assertContains(response, 'Har du synpunkter eller feedback? Skriv gärna till oss här.')

    def test_page_shows_admin_edited_intro_text(self):
        feedback_settings = FeedbackFormSettings.get_solo()
        feedback_settings.intro_text = 'Berätta vad du tycker om oss!'
        feedback_settings.save()

        response = self.client.get(reverse('feedback:form'))

        self.assertContains(response, 'Berätta vad du tycker om oss!')

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_valid_submission_saves_and_notifies_recipients(self, _mock_captcha, mock_send_email):
        FeedbackEmailRecipient.objects.create(recipient_email='feedback@example.com')

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('feedback:form'),
                {
                    'email': 'visitor@example.com',
                    'message': 'Nice site',
                    'cf-turnstile-response': 'token',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackSubmission.objects.count(), 1)
        mock_send_email.delay.assert_called_once()
        self.assertEqual(mock_send_email.delay.call_args.args[3], ['feedback@example.com'])

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_success_page_shown_after_submission(self, _mock_captcha, _mock_send_email):
        self.client.post(reverse('feedback:form'), {'message': 'Nice site', 'cf-turnstile-response': 'token'})

        response = self.client.get(reverse('feedback:form'))

        self.assertContains(response, 'Tack för ditt svar')

    @patch('feedback.views.validate_captcha')
    def test_invalid_form_never_calls_validate_captcha(self, mock_validate_captcha):
        # Matches harassment.views.harassment_form's short-circuit: an
        # invalid submission shouldn't trigger the outbound Cloudflare call
        # at all, not just skip acting on its result.
        self.client.post(reverse('feedback:form'), {'message': '', 'cf-turnstile-response': 'token'})

        mock_validate_captcha.assert_not_called()

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_no_email_enqueued_without_configured_recipients(self, _mock_captcha, mock_send_email):
        self.client.post(reverse('feedback:form'), {'message': 'Something to say', 'cf-turnstile-response': 'token'})

        self.assertEqual(FeedbackSubmission.objects.count(), 1)
        mock_send_email.delay.assert_not_called()


class FeedbackAdminTests(TestCase):
    def test_message_preview_truncates_long_messages(self):
        submission = FeedbackSubmission.objects.create(message='x' * 100)
        submission_admin = FeedbackSubmissionAdmin(FeedbackSubmission, admin.site)

        preview = submission_admin.message_preview(submission)

        self.assertEqual(preview, 'x' * 80 + '...')

    def test_message_preview_leaves_short_messages_untouched(self):
        submission = FeedbackSubmission.objects.create(message='short')
        submission_admin = FeedbackSubmissionAdmin(FeedbackSubmission, admin.site)

        self.assertEqual(submission_admin.message_preview(submission), 'short')


class FeedbackFormSettingsAdminTests(TestCase):
    def test_get_solo_creates_the_singleton_row_once(self):
        first = FeedbackFormSettings.get_solo()
        second = FeedbackFormSettings.get_solo()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FeedbackFormSettings.objects.count(), 1)

    def test_add_permission_is_refused_once_the_row_exists(self):
        request = SimpleNamespace(user=SimpleNamespace(has_perm=Mock(return_value=True)))
        settings_admin = FeedbackFormSettingsAdmin(FeedbackFormSettings, admin.site)

        FeedbackFormSettings.get_solo()

        self.assertFalse(settings_admin.has_add_permission(request))

    def test_delete_permission_is_always_refused(self):
        settings_admin = FeedbackFormSettingsAdmin(FeedbackFormSettings, admin.site)

        self.assertFalse(settings_admin.has_delete_permission(request=None))
