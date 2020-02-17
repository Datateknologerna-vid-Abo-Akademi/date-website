from django import forms
from django.forms.widgets import PasswordInput, TextInput



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
        member.set_password(self.cleaned_data['password'])
            # TODO: send password creation email to member
        if commit:
            member.update_or_create(pk=member.pk)
            logger.debug("Saved new member:", member)
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
            member.update_or_create(pk=member.pk)
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
            subscription_payment.update_or_create(pk=subscription_payment.pk)
            logger.debug("SubscriptionPayment saved")
        return subscription_payment
