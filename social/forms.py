from django import forms
from .models import Harassment


class HarassmentForm(forms.ModelForm):
    class Meta:
        model = Harassment
        fields = ['email', 'message']

    def __init__(self, *args, **kwargs):
        super(HarassmentForm, self).__init__(*args, **kwargs)
        # Add a class to the 'message' field
        self.fields['message'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})