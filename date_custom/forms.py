from django.forms import ModelForm

from date_custom.models import MembershipSignupRequest


class MembershipSignupForm(ModelForm):

    class Meta:
        model = MembershipSignupRequest
        exclude = ('created_at', 'created_by')
