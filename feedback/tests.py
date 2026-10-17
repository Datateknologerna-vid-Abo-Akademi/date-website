from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from feedback.admin import FeedbackFormSettingsAdmin, FeedbackSubmissionAdmin
from feedback.models import DEFAULT_INTRO_TEXT, FeedbackEmailRecipient, FeedbackFormSettings, FeedbackSubmission

# Distinctive enough that a leak cannot be confused with unrelated page text.
# Mirrors harassment.tests.REPORT_TEXT - see HarassmentAdminLogRedactionTests.
FEEDBACK_TEXT = "En unik text som aldrig får hamna i administrationsloggen"


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
                    'consent': 'on',
                    'cf-turnstile-response': 'token',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackSubmission.objects.count(), 1)
        mock_send_email.delay.assert_called_once()
        self.assertEqual(mock_send_email.delay.call_args.args[3], ['feedback@example.com'])
        # The notification body carries the admin link only: the message text
        # must not travel in an email any wider than the recipient list.
        body = mock_send_email.delay.call_args.args[2]
        self.assertNotIn('Nice site', body)

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
        with self.assertLogs('date', level='WARNING') as logs, self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('feedback:form'), {'message': 'Something to say', 'cf-turnstile-response': 'token'}
            )

        self.assertEqual(FeedbackSubmission.objects.count(), 1)
        mock_send_email.delay.assert_not_called()
        self.assertTrue(
            any('No feedback recipients configured' in message for message in logs.output),
            logs.output,
        )

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=False)
    def test_rejected_captcha_saves_nothing(self, _mock_captcha, mock_send_email):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('feedback:form'),
                {
                    'email': 'visitor@example.com',
                    'message': 'Nice site',
                    'consent': 'on',
                    'cf-turnstile-response': 'token',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedbackSubmission.objects.count(), 0)
        mock_send_email.delay.assert_not_called()

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=False)
    def test_rejected_captcha_explains_itself_on_the_rendered_form(self, _mock_captcha, _mock_send_email):
        response = self.client.post(
            reverse('feedback:form'),
            {
                'email': 'visitor@example.com',
                'message': 'Nice site',
                'consent': 'on',
                'cf-turnstile-response': 'token',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Robotkontrollen misslyckades. Försök igen.')

    def test_invalid_form_renders_its_field_errors(self):
        response = self.client.post(reverse('feedback:form'), {'message': '', 'email': 'not-an-email'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedbackSubmission.objects.count(), 0)
        self.assertContains(response, 'errorlist')
        self.assertContains(response, 'Detta fält måste fyllas i.')
        self.assertContains(response, 'Fyll i en giltig e-postadress.')


class FeedbackFormSuccessFlagTests(TestCase):
    """The thank-you flag is consumed on GET only. Checking it before the POST
    branch swallowed a submission whenever the redirect GET never landed (back
    button, dropped connection, a second tab) - see feedback/views.py and the
    matching fix in harassment/views.py."""

    def submit(self, message='Nice site'):
        return self.client.post(
            reverse('feedback:form'),
            {'message': message, 'cf-turnstile-response': 'token'},
        )

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_success_page_is_shown_once_and_the_get_consumes_the_flag(self, _mock_captcha, _mock_send_email):
        self.submit()

        success = self.client.get(reverse('feedback:form'))
        self.assertContains(success, 'Tack för ditt svar')

        # The flag was consumed by the GET above: the next GET is the form.
        again = self.client.get(reverse('feedback:form'))
        self.assertContains(again, 'Meddelande')
        self.assertNotContains(again, 'Tack för ditt svar')

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_post_while_the_success_flag_is_set_is_still_saved(self, _mock_captcha, _mock_send_email):
        # The redirect GET never landed, so the flag is still in the session.
        session = self.client.session
        session['feedback_submitted'] = True
        session.save()

        response = self.submit('En andra inskickning')

        # A POST is validated and saved, not answered with the thank-you page.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackSubmission.objects.count(), 1)
        self.assertEqual(FeedbackSubmission.objects.get().message, 'En andra inskickning')


class FeedbackFormConsentTests(TestCase):
    """The optional email is personal data, so the form shows the same consent
    checkbox as the harassment form and enforces it server side - see
    feedback/forms.py and templates/common/feedback/feedback_form.html."""

    def post(self, **extra):
        return self.client.post(
            reverse('feedback:form'),
            {'message': 'Nice site', 'cf-turnstile-response': 'token', **extra},
        )

    def test_form_page_shows_the_consent_checkbox_and_the_terms_link(self):
        response = self.client.get(reverse('feedback:form'))

        self.assertContains(response, 'name="consent"')
        self.assertContains(response, '/pages/registerbeskrivning/')

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_email_without_consent_is_rejected_and_saves_nothing(self, mock_validate_captcha, mock_send_email):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post(email='visitor@example.com')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedbackSubmission.objects.count(), 0)
        self.assertContains(response, 'Detta fält måste fyllas i.')
        # The invalid submission never reaches the outbound Cloudflare call.
        mock_validate_captcha.assert_not_called()
        mock_send_email.delay.assert_not_called()

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_message_without_email_needs_no_consent(self, _mock_captcha, _mock_send_email):
        response = self.post()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackSubmission.objects.count(), 1)

    @patch('feedback.views.send_email_task')
    @patch('feedback.views.validate_captcha', return_value=True)
    def test_email_with_consent_is_accepted(self, _mock_captcha, _mock_send_email):
        response = self.post(email='visitor@example.com', consent='on')

        self.assertEqual(response.status_code, 302)
        submission = FeedbackSubmission.objects.get()
        self.assertEqual(submission.email, 'visitor@example.com')
        self.assertEqual(submission.message, 'Nice site')


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
    """A fresh test database already holds the row seeded by
    feedback/migrations/0003_seed_feedbackformsettings.py, so tests that need an
    empty table delete it on purpose rather than assuming no rows exist."""

    @staticmethod
    def clear_seeded_rows():
        FeedbackFormSettings.objects.all().delete()

    def test_the_seeding_migration_creates_the_row_the_page_reads(self):
        obj = FeedbackFormSettings.objects.get()

        self.assertEqual(obj.intro_text_sv, DEFAULT_INTRO_TEXT)
        self.assertContains(self.client.get(reverse('feedback:form')), DEFAULT_INTRO_TEXT)

    def test_get_solo_returns_the_seeded_row_without_creating_another(self):
        first = FeedbackFormSettings.get_solo()
        second = FeedbackFormSettings.get_solo()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FeedbackFormSettings.objects.count(), 1)

    def test_get_solo_recreates_the_row_when_it_is_missing(self):
        self.clear_seeded_rows()

        obj = FeedbackFormSettings.get_solo()

        self.assertEqual(obj.intro_text_sv, DEFAULT_INTRO_TEXT)
        self.assertEqual(FeedbackFormSettings.objects.count(), 1)
        self.assertContains(self.client.get(reverse('feedback:form')), DEFAULT_INTRO_TEXT)

    def test_get_intro_text_does_not_create_the_row(self):
        self.clear_seeded_rows()

        self.assertEqual(FeedbackFormSettings.get_intro_text(), DEFAULT_INTRO_TEXT)
        self.assertEqual(FeedbackFormSettings.objects.count(), 0)

    def test_get_intro_text_reads_the_lowest_pk_row(self):
        self.clear_seeded_rows()
        FeedbackFormSettings.objects.create(pk=3, intro_text='Lägsta pk')
        FeedbackFormSettings.objects.create(pk=7, intro_text='Högre pk')

        self.assertEqual(FeedbackFormSettings.get_intro_text(), 'Lägsta pk')

    def test_get_solo_returns_a_row_created_out_of_band_at_another_pk(self):
        self.clear_seeded_rows()
        FeedbackFormSettings.objects.create(pk=7, intro_text='Skapad vid sidan av admin')

        solo = FeedbackFormSettings.get_solo()

        self.assertEqual(solo.pk, 7)
        self.assertEqual(solo.intro_text_sv, 'Skapad vid sidan av admin')

    def test_out_of_band_row_is_what_the_form_page_renders(self):
        self.clear_seeded_rows()
        FeedbackFormSettings.objects.create(pk=7, intro_text='Skapad vid sidan av admin')

        response = self.client.get(reverse('feedback:form'))

        self.assertContains(response, 'Skapad vid sidan av admin')

    def test_add_permission_is_refused_once_the_row_exists(self):
        request = SimpleNamespace(user=SimpleNamespace(has_perm=Mock(return_value=True)))
        settings_admin = FeedbackFormSettingsAdmin(FeedbackFormSettings, admin.site)

        FeedbackFormSettings.get_solo()

        self.assertFalse(settings_admin.has_add_permission(request))

    def test_delete_permission_is_always_refused(self):
        settings_admin = FeedbackFormSettingsAdmin(FeedbackFormSettings, admin.site)

        self.assertFalse(settings_admin.has_delete_permission(request=None))

    def test_the_seeded_row_fills_only_the_swedish_column(self):
        # Pre-filling en/fi with the same text as sv would make an untranslated
        # row look already translated when an admin opens those tabs.
        obj = FeedbackFormSettings.objects.get()

        self.assertEqual(obj.intro_text_sv, DEFAULT_INTRO_TEXT)
        self.assertEqual(obj.intro_text_en, '')
        self.assertEqual(obj.intro_text_fi, '')

    def test_get_solo_recreates_only_the_swedish_column(self):
        self.clear_seeded_rows()

        obj = FeedbackFormSettings.get_solo()

        self.assertEqual(obj.intro_text_sv, DEFAULT_INTRO_TEXT)
        self.assertEqual(obj.intro_text_en, '')
        self.assertEqual(obj.intro_text_fi, '')

    def test_blank_translations_fall_back_to_swedish(self):
        obj = FeedbackFormSettings.get_solo()

        for language in ('sv', 'en', 'fi'):
            with translation.override(language):
                self.assertEqual(obj.intro_text, DEFAULT_INTRO_TEXT)


class FeedbackFormSettingsAdminChangelistTests(TestCase):
    """The editable row and the row the site reads must not diverge: the
    changelist is pinned to the solo (lowest pk) row."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='feedbacksettingsadmin',
            email='feedbacksettingsadmin@example.com',
            password='pass',
        )

    def setUp(self):
        self.client.force_login(self.admin_user, backend='members.backends.AuthBackend')

    @staticmethod
    def clear_seeded_rows():
        # The 0003 data migration seeds a row, so drop it to exercise the
        # empty-table cases these tests are about.
        FeedbackFormSettings.objects.all().delete()

    def test_changelist_shows_only_the_solo_row(self):
        self.clear_seeded_rows()
        FeedbackFormSettings.objects.create(pk=3, intro_text='Lägsta pk')
        FeedbackFormSettings.objects.create(pk=8, intro_text='Högre pk')

        response = self.client.get(reverse('admin:feedback_feedbackformsettings_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([obj.pk for obj in response.context['cl'].result_list], [3])

    def test_changelist_does_not_create_the_row_on_a_get(self):
        self.clear_seeded_rows()

        response = self.client.get(reverse('admin:feedback_feedbackformsettings_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FeedbackFormSettings.objects.count(), 0)

    def test_non_solo_row_is_not_editable(self):
        self.clear_seeded_rows()
        FeedbackFormSettings.objects.create(pk=3, intro_text='Lägsta pk')
        FeedbackFormSettings.objects.create(pk=8, intro_text='Högre pk')

        response = self.client.get(reverse('admin:feedback_feedbackformsettings_change', args=[8]))

        self.assertEqual(response.status_code, 302)


class FeedbackFormSettingsAdminWithoutLanguageFeaturesTests(TestCase):
    """With ENABLE_LANGUAGE_FEATURES off (the default for most associations) the
    site runs Swedish only and the public page reads intro_text_sv. The change
    form must edit exactly that column: the base intro_text column is not what
    the site reads, and modeltranslation syncs it from the active language
    column on save, so an edit typed into it is silently discarded. See
    feedback/admin.py."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='feedbacksettingslangadmin',
            email='feedbacksettingslangadmin@example.com',
            password='pass',
        )

    def setUp(self):
        self.client.force_login(self.admin_user, backend='members.backends.AuthBackend')
        self.settings_row = FeedbackFormSettings.objects.get()
        self.change_url = reverse('admin:feedback_feedbackformsettings_change', args=[self.settings_row.pk])

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_change_form_edits_only_the_column_the_site_reads(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="intro_text_sv"')
        self.assertNotContains(response, 'name="intro_text"')
        self.assertNotContains(response, 'name="intro_text_en"')
        self.assertNotContains(response, 'name="intro_text_fi"')

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_edited_text_is_rendered_by_the_public_form_page(self):
        response = self.client.post(self.change_url, {'intro_text_sv': 'Ändrad text', '_save': 'Save'})

        self.assertEqual(response.status_code, 302)
        self.settings_row.refresh_from_db()
        self.assertEqual(self.settings_row.intro_text_sv, 'Ändrad text')
        page = self.client.get(reverse('feedback:form'))
        self.assertContains(page, 'Ändrad text')
        self.assertNotContains(page, DEFAULT_INTRO_TEXT)

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_get_fields_returns_only_the_column_the_site_reads(self):
        model_admin = admin.site._registry[FeedbackFormSettings]
        request = SimpleNamespace()

        self.assertEqual(model_admin.get_fields(request), ['intro_text_sv'])

    @override_settings(ENABLE_LANGUAGE_FEATURES=True)
    def test_change_form_keeps_the_language_fields_when_features_are_enabled(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="intro_text_sv"')
        self.assertContains(response, 'name="intro_text_en"')


class FeedbackAdminLogRedactionTests(TestCase):
    """Message text must never reach the admin log, which non-recipients can
    read. Mirrors harassment.tests.HarassmentAdminLogRedactionTests."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='feedbacklogadmin',
            email='feedbacklogadmin@example.com',
            password='pass',
        )

    def setUp(self):
        self.client.force_login(self.admin_user, backend='members.backends.AuthBackend')

    def test_str_identifies_the_submission_without_its_content(self):
        submission = FeedbackSubmission.objects.create(message=FEEDBACK_TEXT)

        label = str(submission)

        self.assertNotIn(FEEDBACK_TEXT, label)
        self.assertIn(f'#{submission.pk}', label)

    def test_admin_add_change_and_delete_keep_message_text_out_of_the_log(self):
        response = self.client.post(
            reverse('admin:feedback_feedbacksubmission_add'),
            {'email': 'reporter@example.com', 'message': FEEDBACK_TEXT, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)
        submission = FeedbackSubmission.objects.get()

        response = self.client.post(
            reverse('admin:feedback_feedbacksubmission_change', args=[submission.pk]),
            {'email': 'reporter@example.com', 'message': f'{FEEDBACK_TEXT} (uppdaterad)', '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse('admin:feedback_feedbacksubmission_delete', args=[submission.pk]),
            {'post': 'yes'},
        )
        self.assertEqual(response.status_code, 302)

        entries = list(LogEntry.objects.all())
        self.assertEqual(len(entries), 3)
        for entry in entries:
            self.assertNotIn(FEEDBACK_TEXT, entry.object_repr)
            self.assertNotIn(FEEDBACK_TEXT, entry.get_change_message())

    def test_admin_log_page_does_not_render_message_text(self):
        response = self.client.post(
            reverse('admin:feedback_feedbacksubmission_add'),
            {'email': 'reporter@example.com', 'message': FEEDBACK_TEXT, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)
        submission = FeedbackSubmission.objects.get()

        response = self.client.get(reverse('admin:admin_logentry_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, FEEDBACK_TEXT)
        self.assertContains(response, f'#{submission.pk}')
