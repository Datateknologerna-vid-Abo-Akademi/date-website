from smtplib import SMTPException
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.utils import VALIDATION_URL, send_email_task, validate_captcha


class ValidateCaptchaTests(SimpleTestCase):
    @override_settings(TURNSTILE_SECRET_KEY='')
    def test_returns_true_when_secret_missing(self):
        self.assertTrue(validate_captcha('any-token'))

    @override_settings(TURNSTILE_SECRET_KEY='secret')
    def test_returns_false_when_response_missing(self):
        self.assertFalse(validate_captcha(''))

    @override_settings(TURNSTILE_SECRET_KEY='secret')
    @patch('core.utils.requests.post')
    def test_returns_true_on_successful_validation(self, mock_post):
        mock_post.return_value.json.return_value = {'success': True}
        self.assertTrue(validate_captcha('token'))
        mock_post.assert_called_once_with(VALIDATION_URL, data={'secret': 'secret', 'response': 'token'})

    @override_settings(TURNSTILE_SECRET_KEY='secret')
    @patch('core.utils.requests.post', side_effect=Exception('boom'))
    def test_returns_false_on_request_exception(self, _):
        self.assertFalse(validate_captcha('token'))


class SendEmailTaskTests(SimpleTestCase):
    @patch('core.utils.send_mail')
    def test_calls_send_mail_with_arguments(self, mock_send_mail):
        send_email_task('subject', 'body', 'from@example.com', ['to@example.com'])
        mock_send_mail.assert_called_once_with('subject', 'body', 'from@example.com', ['to@example.com'])

    @patch('core.utils.logger')
    @patch('core.utils.send_mail', side_effect=SMTPException('fail'))
    def test_logs_error_when_send_mail_fails(self, mock_send_mail, mock_logger):
        send_email_task('subject', 'body', 'from@example.com', ['to@example.com'])
        mock_send_mail.assert_called_once()
        mock_logger.error.assert_called_once()
