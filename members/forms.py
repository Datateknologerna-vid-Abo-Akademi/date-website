from django import forms
from django.forms.widgets import PasswordInput, TextInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


from dateutil.relativedelta import relativedelta

from members.models import Member, SubscriptionPayment, SUB_RE_SCALE_YEAR, SUB_RE_SCALE_MONTH, SUB_RE_SCALE_DAY

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
            'password',
            'groups',
        )

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
            'groups',
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


class SubscriptionPaymentForm(forms.ModelForm):

    class Meta:
        model = SubscriptionPayment
        fields = (
            'member',
            'subscription',
            'date_paid',
            'amount_paid',
        )

    def save(self, commit=True):
        subscription_payment = super(SubscriptionPaymentForm, self).save(commit=False)
        if subscription_payment.subscription.does_expire:
            date_paid = subscription_payment.date_paid
            sub_duration = subscription_payment.subscription.renewal_period
            sub_duration_type = subscription_payment.subscription.renewal_scale
            delta = 0
            if sub_duration_type == SUB_RE_SCALE_DAY:
                delta = relativedelta(days=+sub_duration)
            elif sub_duration_type == SUB_RE_SCALE_MONTH:
                delta = relativedelta(months=+sub_duration)
            elif sub_duration_type == SUB_RE_SCALE_YEAR:
                delta = relativedelta(years=+sub_duration)
            subscription_payment.date_expires = date_paid + delta
            logger.debug("Calculated expiry date for subscription: {}".format(subscription_payment.date_expires))
        if commit:
            subscription_payment.save()
            logger.debug("SubscriptionPayment saved")
        return subscription_payment


class SignUpForm(forms.ModelForm):
    # send_email = forms.BooleanField(required=False)
    username = forms.CharField(help_text='detta fält är inte obligatoriskt')
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        min_length=8,
        error_messages={'required': 'Password is required'},
        help_text='detta fält är inte obligatoriskt'
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
            'membership_type'
        )

    def save(self, commit=True):
        member = super(SignUpForm, self).save(commit=False)
        # if not '@abo.fi' in self.cleaned_data['email']:
        # logger.debug('Setting member password')
        member.set_password(self.cleaned_data['password1'])
        # else:
        # TODO: send password creation email to member
        # pass
        if commit:
            member.save()
            logger.debug("Saved", member)
        return member
