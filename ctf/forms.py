import logging

from django import forms

logger = logging.getLogger("date")


class FlagForm(forms.Form):
    flag = forms.CharField(label="Insert Flag", max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = kwargs.get("initial", {})
        if initial and initial.get("disable_field"):
            self.fields[initial["disable_field"]].disabled = True
