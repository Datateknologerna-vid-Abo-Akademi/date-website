from django.forms import ModelForm

from date_custom.models import MembershipSignupRequest


class MembershipSignupForm(ModelForm):

    class Meta:
        model = MembershipSignupRequest
        fields = [field.name for field in MembershipSignupRequest._meta.fields if field.name not in (
            'created_at', 'created_by')]
