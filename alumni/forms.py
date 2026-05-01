from django import forms
from django.utils.translation import gettext_lazy as _

class AlumniSignUpForm(forms.Form):
    tfif_choices = (
        ('ja', 'Ja'),
        ('nej', 'Nej'),
        ('vet inte', 'Vet inte')
    )
    operation_choices = (
        ('CREATE', 'Registrera mig som ny medlem'),
        ('UPDATE', 'Uppdatera mina uppgifter'),
    )

    firstname = forms.CharField(max_length=100, required=True, help_text=_('detta fält är obligatoriskt'), label=_('Förnamn'))
    lastname = forms.CharField(max_length=100, required=True, help_text=_('detta fält är obligatoriskt'), label=_('Efternamn'))
    email = forms.EmailField(max_length=320, help_text=_('detta fält är obligatoriskt'), label=_('E-postadress'),
                             required=True)
    phone_number = forms.CharField(max_length=20, label=_('Telefonnummer'), required=False)
    address = forms.CharField(max_length=200, label=_('Adress'), required=False)
    zip = forms.CharField(max_length=20, label=_('Postnummer'), required=False)
    city = forms.CharField(max_length=200, label=_('Postanstalt'), required=False)
    country = forms.CharField(max_length=200, label=_('Land'), required=False)
    year_of_admission = forms.IntegerField(max_value=3000, label=_('Inskrivningsår'), required=False)
    employer = forms.CharField(max_length=200, label=_('Arbetsplats'), required=False)
    work_title = forms.CharField(max_length=200, label=_('Arbetsuppgift'), required=False)
    tfif_membership = forms.ChoiceField(choices=tfif_choices, label=_('TFiF medlemskap'), required=False)
    alumni_newsletter_consent = forms.BooleanField(label=_('Jag tar gärna emot information om alumnevenemang'),
                                                   required=False)
    operation = forms.ChoiceField(choices=operation_choices, label=_('Jag vill:'),
                                  required=True, initial='CREATE', disabled=True, widget=forms.HiddenInput())
    token = forms.CharField(max_length=50, required=False, label=_('Token'), widget=forms.HiddenInput())

    class Meta:
        fields = (
            'operation',
            'firstname',
            'lastname',
            'email',
            'phone_number',
            'address',
            'zip',
            'city',
            'country',
            'year_of_admission',
            'employer',
            'work_title',
            'tfif_membership',
            'alumni_newsletter_consent',
        )


class AlumniUpdateForm(AlumniSignUpForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['email'].disabled = True
        self.fields['operation'].disabled = True
        self.fields['token'].disabled = True
        self.fields['token'].required = True
        self.fields['operation'].initial = 'UPDATE'
        self.fields['firstname'].required = False
        self.fields['firstname'].help_text = ""
        self.fields['lastname'].required = False
        self.fields['lastname'].help_text = ""

    class Meta(AlumniSignUpForm.Meta):
        fields = AlumniSignUpForm.Meta.fields + ('token',)


class AlumniEmailVerificationForm(forms.Form):
    email = forms.EmailField(max_length=320, help_text=_('detta fält är obligatoriskt'), label=_('E-postadress'),
                             required=True)

    class Meta:
        fields = ('email',)
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': _('Ange din e-postadress')}),
        }
