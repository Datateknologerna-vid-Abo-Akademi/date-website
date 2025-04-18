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

    name = forms.CharField(max_length=200, required=True, help_text=_('detta fält är obligatoriskt'), label=_('Namn'))
    email = forms.EmailField(max_length=320, help_text=_('detta fält är obligatoriskt'), label=_('E-postadress'),
                             required=True)
    phone_number = forms.CharField(max_length=20, label=_('Telefonnummer'), required=False)
    address = forms.CharField(max_length=200, label=_('Adress'), required=False)
    year_of_admission = forms.IntegerField(max_value=3000, label=_('Inskrivningsår'), required=False)
    employer = forms.CharField(max_length=200, label=_('Arbetsplats'), required=False)
    work_title = forms.CharField(max_length=200, label=_('Arbetsuppgift'), required=False)
    tfif_membership = forms.ChoiceField(choices=tfif_choices, label=_('TFiF medlemskap'), required=False)
    alumni_newsletter_consent = forms.BooleanField(label=_('Jag tar gärna emot information om alumnevenemang'),
                                                   required=False)
    operation = forms.ChoiceField(choices=operation_choices, label=_('Jag vill:'),
                                  required=True)

    class Meta:
        fields = (
            'operation',
            'name',
            'email',
            'phone_number',
            'address',
            'year_of_admission',
            'employer',
            'work_title',
            'tfif_membership',
            'alumni_newsletter_consent',
        )
