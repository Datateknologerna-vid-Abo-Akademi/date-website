import logging

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from core.utils import send_email_task

from .managers import MemberManager

logger = logging.getLogger('date')


FRESHMAN = 1
ORDINARY_MEMBER = 2
SUPPORTING_MEMBER = 3
SENIOR_MEMBER = 4

PERMISSION_PROFILES = (
    (FRESHMAN, _('Gulnäbb')),
    (ORDINARY_MEMBER, _('Ordinarie medlem')),
    (SUPPORTING_MEMBER, _('Stödjande medlem')),
    (SENIOR_MEMBER, _('Seniormedlem')),
)


class Member(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(_('Användarnamn'), unique=True, max_length=20, blank=False)
    email = models.EmailField(_('E-postadress'), unique=True, blank=True, null=True)
    first_name = models.CharField(_('Förnamn'), max_length=30, blank=True)
    last_name = models.CharField(_('Efternamn'), max_length=30, blank=True)
    phone = models.CharField(_('Telefonnummer'), max_length=30, blank=True)
    address = models.CharField(_('Adress'), max_length=50, blank=True)
    zip_code = models.CharField(_('Postkod'), max_length=5, blank=True)
    city = models.CharField(_('Postanstalt'), max_length=30, blank=True)
    country = models.CharField(_('Land'), max_length=30, default=_('Finland'), blank=True)
    membership_type = models.ForeignKey("members.MembershipType", default=FRESHMAN, blank=False, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    objects = MemberManager()

    USERNAME_FIELD = 'username'

    class Meta:
        verbose_name = _('medlem')
        verbose_name_plural = _('medlemmar')
        ordering = ('id',)

    def __unicode__(self):
        return u'{0} ({1})'.format(self.get_full_name(), self.email)

    @property
    def is_staff(self):
        return self.groups.filter(name__in=settings.STAFF_GROUPS).exists() or self.is_superuser

    @property
    def full_name(self):
        return self.get_full_name()

    def get_full_name(self):
        """
        :return: First and last name with space between
        """
        return u'{0} {1}'.format(self.first_name, self.last_name)

    def get_short_name(self):
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends email to members
        """
        send_email_task.delay(subject, message, from_email, [self.email], **kwargs)

    def get_active_subscription(self):
        all_subscriptions = SubscriptionPayment.objects.filter(member=self).exclude(date_expires__lt=timezone.now())
        if len(all_subscriptions) != 0:
            return all_subscriptions[0].subscription
        return None

    def get_str_membership_type(self):
        return self.membership_type.name


class MembershipType(models.Model):
    name = models.CharField(_('Namn'), max_length=200, blank=False)
    description = models.TextField(_('Beskrivning'), blank=True)
    permission_profile = models.IntegerField(_('Behörighetsprofil'), choices=PERMISSION_PROFILES, default=FRESHMAN)

    class Meta:
        verbose_name = _('Medlemskap')
        verbose_name_plural = _('medlemskapstyper')
        ordering = ('id',)

    def __str__(self):
        return self.name


SUB_RE_SCALE_DAY = 'day'
SUB_RE_SCALE_MONTH = 'month'
SUB_RE_SCALE_YEAR = 'year'

SUBSCRIPTION_RENEWAL_SCALES = (
    (SUB_RE_SCALE_DAY, _('Dagar')),
    (SUB_RE_SCALE_MONTH, _('Månader')),
    (SUB_RE_SCALE_YEAR, _('År')),
)


class Subscription(models.Model):
    name = models.CharField(_('Namn'), max_length=200, blank=False)
    does_expire = models.BooleanField(_('Upphör'), default=True)
    renewal_scale = models.CharField(
        _('Förnyelse skala'), max_length=10, choices=SUBSCRIPTION_RENEWAL_SCALES, blank=False, null=True
    )
    renewal_period = models.IntegerField(_('Förnyelseperiod'), blank=True, null=True)
    price = models.DecimalField(_('Pris'), decimal_places=2, max_digits=9, blank=False)

    class Meta:
        verbose_name = _('prenumeration')
        verbose_name_plural = _('prenumerationer')
        ordering = ('id',)

    def __str__(self):
        return self.name


class SubscriptionPayment(models.Model):
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    subscription = models.ForeignKey('members.Subscription', on_delete=models.CASCADE)
    date_paid = models.DateField(_('Betald'), default=timezone.now, blank=False)
    date_expires = models.DateField(_('Upphör'), default=None, blank=True, null=True)
    amount_paid = models.DecimalField(_('Betald summa'), max_digits=9, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _('prenumerationsbetalning')
        verbose_name_plural = _('prenumerationsbetalningar')
        ordering = ('id',)

    def __str__(self):
        return self.member.get_full_name()

    @property
    def is_active(self):
        if self.date_expires is None:
            return True
        return self.date_expires >= timezone.now().date()

    @property
    def expires(self):
        if self.date_expires is None:
            return _('Aldrig')
        return self.date_expires


class AlumniSignUp(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True, max_length=320)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)
    year_of_admission = models.IntegerField(null=True)
    employer = models.CharField(max_length=200, blank=True)
    work_title = models.CharField(max_length=200, blank=True)
    tfif_membership = models.CharField(max_length=50, blank=True)
    alumni_newsletter_consent = models.BooleanField(default=False)
    operation = models.CharField(max_length=200, blank=True)
    # Internal data
    signup_date = models.DateTimeField(_("Registreringsdatum"), auto_now_add=True)
    acknowledge = models.BooleanField(_("Processerad"), default=False)  # For acknowledgement of adding into registry

    class Meta:
        verbose_name = _("Alumnregistrering")
        verbose_name_plural = _("Alumnregistreringar")
        ordering = ('id',)

    def __str__(self):
        return self.name


class AlumniEmailRecipient(models.Model):
    recipient_email = models.EmailField(max_length=256)

    def __str__(self):
        return self.recipient_email

    class Meta:
        verbose_name = _("Emailmottagare för ARG")
        verbose_name_plural = _("Emailmottagare för ARG")


class FunctionaryRole(models.Model):
    title = models.CharField(_('Titel'), max_length=200)
    board = models.BooleanField(_('Styrelse'), default=False)

    class Meta:
        verbose_name = _("Funktionärspost")
        verbose_name_plural = _("Funktionärsposter")

    def __str__(self):
        return self.title


class Functionary(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    functionary_role = models.ForeignKey(FunctionaryRole, on_delete=models.CASCADE)
    year = models.IntegerField(_('Årtal'))
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Funktionär")
        verbose_name_plural = _("Funktionärer")

    def __str__(self):
        return f"{self.member.get_full_name()} {self.functionary_role.title} {self.year}"