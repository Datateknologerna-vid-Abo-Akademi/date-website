from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

from .models import Functionary


class FunctionaryForm(forms.ModelForm):
    year = forms.IntegerField(
        label=_("Årtal"),
        validators=[MinValueValidator(1999)],
        help_text=_("Ange ett år i formatet YYYY"),
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "YYYY"}),
    )

    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop("member", None)
        super().__init__(*args, **kwargs)

    def _post_clean(self):
        if self.member:
            self.instance.member = self.member
        super()._post_clean()

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("year")
        functionary_role = cleaned_data.get("functionary_role")
        member = self.member or (self.instance.member if self.instance else None)

        if Functionary.objects.filter(year=year, functionary_role=functionary_role, member=member).exists():
            raise ValidationError("Du har redan lagt till den här funktionärsposten för det året.")

        return cleaned_data

    class Meta:
        model = Functionary
        fields = ["functionary_role", "year"]
        widgets = {
            "functionary_role": forms.Select(attrs={"class": "form-control"}),
        }


class FunctionaryFilterForm(forms.Form):
    year = forms.IntegerField(required=False)
    functionary_role = forms.CharField(required=False)
