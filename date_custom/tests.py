from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from date_custom.forms import MembershipSignupForm
from date_custom.models import MembershipSignupRequest
from members.models import Member


class MembershipSignupRequestViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Member.objects.create_user(
            username='applicant', password='secret', email='applicant@example.com')

    def setUp(self):
        self.url = reverse('date_custom:membership_signup_request')

    def test_login_is_required(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response, f'/members/login?next={self.url}', fetch_redirect_response=False)

    @patch('date_custom.views.validate_captcha', return_value=False)
    def test_invalid_captcha_does_not_create_request(self, validate_captcha):
        self.client.force_login(self.user)

        response = self.client.post(self.url, self.valid_form_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Captcha-valideringen misslyckades')
        self.assertFalse(MembershipSignupRequest.objects.exists())
        validate_captcha.assert_called_once_with('')

    @patch('date_custom.views.validate_captcha', return_value=True)
    def test_created_request_is_linked_to_logged_in_member(self, validate_captcha):
        self.client.force_login(self.user)
        data = self.valid_form_data()
        data['cf-turnstile-response'] = 'valid-token'

        response = self.client.post(self.url, data)

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        request = MembershipSignupRequest.objects.get()
        self.assertEqual(request.created_by, self.user)
        validate_captcha.assert_called_once_with('valid-token')

    def test_form_does_not_expose_managed_fields(self):
        fields = MembershipSignupForm().fields

        self.assertNotIn('id', fields)
        self.assertNotIn('created_at', fields)
        self.assertNotIn('created_by', fields)

    @staticmethod
    def valid_form_data():
        return {
            'full_name': 'Test Applicant',
            'birth_date': '2000-01-02',
            'matriculation_number': '12345',
            'street_address': 'Test Street 1',
            'postal_code': '20500',
            'city': 'Turku',
            'phone_number': '0401234567',
            'email': 'applicant@example.com',
            'website': '',
            'next_of_kin': 'Test Relative 0407654321',
            'processor_speed': '',
            'willing_to_work': 'on',
            'newsletter_consent': 'on',
            'personal_data_sharing_nonconsent': 'on',
            'membership_type': 'ordinary',
        }
