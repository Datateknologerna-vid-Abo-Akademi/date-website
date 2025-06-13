from django.test import TestCase

from members.forms import MemberCreationForm, SignUpForm
from members.models import MembershipType, ORDINARY_MEMBER


class UsernameValidatorTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)

    def test_member_creation_form_accepts_valid_username(self):
        form = MemberCreationForm(data={
            'username': 'valid_user',
            'email': 'valid@example.com',
            'first_name': 'Valid',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertTrue(form.is_valid())

    def test_member_creation_form_rejects_invalid_username(self):
        form = MemberCreationForm(data={
            'username': 'invalid user',
            'email': 'user@example.com',
            'first_name': 'Invalid',
            'last_name': 'User',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_signup_form_rejects_invalid_username(self):
        form = SignUpForm(data={
            'username': 'bad!name',
            'email': 'user@example.com',
            'first_name': 'Bad',
            'last_name': 'Name',
            'membership_type': self.membership_type.id,
            'password': 'secret123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

