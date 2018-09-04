from django import forms

from members.models import Member

import logging

logger = logging.getLogger('date')


class MemberCreationForm(forms.ModelForm):

    send_email = forms.BooleanField(required=False)

    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        min_length=8,
        error_messages={'required': 'Password is required'}
    )

    class Meta:
        model = Member
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'address',
            'zip_code',
            'city',
            'country',
            'membership_type',
            'password'
        )

    # def clean(self):
    #     cleaned = self.cleaned_data
    #     if cleaned.get('send_email') is False and not cleaned.get("password"):
    #         self._errors['password'] = self.error_class(["Password is required if not sending email"])
    #         del cleaned['password']
    #     else:
    #         return cleaned

    def save(self, commit=True):
        member = super(MemberCreationForm, self).save(commit=False)
        #if not '@abo.fi' in self.cleaned_data['email']:
            #logger.debug('Setting member password')
        member.set_password(self.cleaned_data['password'])
        #else:
            # TODO: send password creation email to member
            #pass
        if commit:
            member.save()
            logger.debug("Saved", member)
        return member


class MemberUpdateForm(forms.ModelForm):

    class Meta:
        model = Member
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'address',
            'zip_code',
            'city',
            'country',
            'membership_type',
        )

    def save(self, commit=True):
        member = super(MemberUpdateForm, self).save(commit=False)
        # password = self.cleaned_data["password"]
        password = None
        if password:
            member.set_password(password)
        if commit:
            member.save()
        return member
