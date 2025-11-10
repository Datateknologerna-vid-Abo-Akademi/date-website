import datetime
import logging

from dateutil.relativedelta import relativedelta
from django import forms
from django.conf import settings
from django.contrib.auth.forms import ReadOnlyPasswordHashField, PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.template import loader
from django.utils.translation import gettext_lazy as _

from core.utils import send_email_task
from members.models import (SUB_RE_SCALE_DAY, SUB_RE_SCALE_MONTH,
                            SUB_RE_SCALE_YEAR, Member, SubscriptionPayment, Functionary)

logger = logging.getLogger('date')

# Restrict usernames to ASCII letters, underscores, and hyphens
USERNAME_VALIDATOR = RegexValidator(
    r'^[a-zA-Z_-]+$',
    _('Enter a valid username consisting only of letters, underscores, and hyphens.')
)


class MemberCreationForm(forms.ModelForm):
    send_email = forms.BooleanField(required=False)
    year_of_admission = forms.IntegerField(initial=lambda: datetime.datetime.now().year, required=False, label=_('Inskrivningsår'))

    username = forms.CharField(
        max_length=20,
        validators=[USERNAME_VALIDATOR],
        label=_('Användarnamn'),
    )

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
            'year_of_admission',
            'password',
            'groups',
        )

    def save(self, commit=True):
        member = super(MemberCreationForm, self).save(commit=False)
        member.set_password(self.cleaned_data['password'])
        if commit:
            member.save()
            logger.debug("Saved new member: %s", member)
        return member


class AdminMemberUpdateForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Lösenord",
                                         help_text=("Raw passwords are not stored, so there is no way to see "
                                                    "this user's password, but you can change the password "
                                                    "using <a href=\"../password/\">this form</a>."))

    username = forms.CharField(
        max_length=20,
        validators=[USERNAME_VALIDATOR],
        label=_('Användarnamn'),
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
            'groups',
            'password',
        )

    def save(self, commit=True):
        member = super(AdminMemberUpdateForm, self).save(commit=False)
        password = None
        if password:
            member.set_password(password)
        if commit:
            member.save()
        return member


class CustomPasswordResetForm(PasswordResetForm):

    def send_mail(
            self,
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name=None,
    ):
        context.update(settings.CONTENT_VARIABLES)

        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        from_email = from_email or settings.DEFAULT_FROM_EMAIL

        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            send_email_task.delay(subject, body, from_email, [to_email], html_message=html_email)
        else:
            send_email_task.delay(subject, body, from_email, [to_email])


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
    username = forms.CharField(
        max_length=20,
        validators=[USERNAME_VALIDATOR],
        help_text=_('detta fält är obligatoriskt'),
        label=_('Användarnamn')
    )
    email = forms.EmailField(max_length=200, help_text=_('detta fält är obligatoriskt'), label=_('E-postadress'))
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        min_length=8,
        error_messages={'required': 'Password is required'},
        help_text=_('detta fält är obligatoriskt'),
        label=_('Lösenord')
    )
    first_name = forms.CharField(max_length=100, required=True, label=_('Förnamn'))
    last_name = forms.CharField(max_length=100, required=True, label=_('Efternamn'))
    year_of_admission = forms.IntegerField(initial=lambda: datetime.datetime.now().year, required=False, label=_('Inskrivningsår'))

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
            'year_of_admission',
            'password'
        )



class SubscriptionPaymentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if not obj.first_name or not obj.last_name:
            return obj.username
        return f'{obj.first_name} {obj.last_name}'


class FunctionaryForm(forms.ModelForm):
    year = forms.IntegerField(
        label=_('Årtal'),
        validators=[MinValueValidator(1999)],
        help_text=_('Ange ett år i formatet YYYY'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'YYYY'})
    )

    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        functionary_role = cleaned_data.get('functionary_role')
        member = self.member or (self.instance.member if self.instance else None)

        if Functionary.objects.filter(year=year, functionary_role=functionary_role, member=member).exists():
            raise ValidationError("Du har redan lagt till den här funktionärsposten för det året.")

        return cleaned_data

    class Meta:
        model = Functionary
        fields = ['functionary_role', 'year']
        widgets = {
            'functionary_role': forms.Select(attrs={'class': 'form-control'}),
        }


class FunctionaryFilterForm(forms.Form):
    year = forms.IntegerField(required=False)
    functionary_role = forms.CharField(required=False)


class MemberEditForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = Member
        fields = ['first_name', 'last_name', 'phone', 'address', 'zip_code', 'city', 'country']
