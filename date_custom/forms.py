from django.forms import ModelForm

from date_custom.models import MembershipSignupRequest


class MembershipSignupForm(ModelForm):
    class Meta:
        model = MembershipSignupRequest
        fields = (
            'full_name',
            'birth_date',
            'matriculation_number',
            'street_address',
            'postal_code',
            'city',
            'phone_number',
            'email',
            'website',
            'next_of_kin',
            'processor_speed',
            'willing_to_work',
            'newsletter_consent',
            'personal_data_sharing_nonconsent',
            'membership_type',
        )
