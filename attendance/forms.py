from django import forms

from . import models


# Only used for validation, template must contain necessary inputs!
class AttendanceChangeForm(forms.Form):
    non_member_name = forms.CharField(max_length=models.NON_MEMBER_MAX_NAME_LEN, required=False)
    type = forms.TypedChoiceField(choices=models.AttendanceChange.Type, coerce=lambda x: models.AttendanceChange.Type(int(x)))
    secret = forms.CharField(required=False)

