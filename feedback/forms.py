from django import forms

from .models import FeedbackSubmission


class FeedbackSubmissionForm(forms.ModelForm):
    class Meta:
        model = FeedbackSubmission
        fields = ['email', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
