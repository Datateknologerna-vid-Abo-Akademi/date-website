from django import forms
from django.utils.translation import gettext_lazy as _

from .models import FeedbackSubmission


class FeedbackSubmissionForm(forms.ModelForm):
    # Data-processing consent for the optional email. Deliberately not a model
    # field: consent is a condition for accepting the submission, not data
    # stored with it. Rendered next to the checkbox in
    # templates/common/feedback/feedback_form.html.
    consent = forms.BooleanField(
        required=False,
        label=_('Jag godkänner'),
    )

    class Meta:
        model = FeedbackSubmission
        fields = ['email', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        # The message alone needs no consent: it is the optional email that is
        # personal data, so consent is required exactly when an email is filled
        # in. Reuse the field's own "required" message so the checkbox explains
        # itself the same way every other required field does.
        if cleaned_data.get('email') and not cleaned_data.get('consent'):
            self.add_error('consent', self.fields['consent'].error_messages['required'])
        return cleaned_data
