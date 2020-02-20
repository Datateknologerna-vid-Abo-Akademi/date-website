import logging

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.db import models

from core import settings

logger = logging.getLogger('date')


class MemberManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, password, **extra_fields):
        """
        Creates and saves members with email and password
        """
        if not username:
            raise ValueError('Username is required')
        member = self.model(username=username, **extra_fields)
        member.set_password(password)
        member.save(using=self._db)
        return member

    def create_user(self, username, password=None, **extra_fields):
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        # extra_fields.setdefault('is_staff', True)

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(username, password, **extra_fields)


FRESHMAN = 1
ORDINARY_MEMBER = 2
SUPPORTING_MEMBER = 3
SENIOR_MEMBER = 4

MEMBERSHIP_TYPES = (
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
    membership_type = models.IntegerField(_('Medlemskap'), default=FRESHMAN, choices=MEMBERSHIP_TYPES, blank=False)
    is_active = models.BooleanField(default=True)
    objects = MemberManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

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
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def get_active_subscription(self):
        all_subscriptions = SubscriptionPayment.objects\
            .filter(member=self, date_expires__gte=timezone.now, date_expires__isnull=True)\
            .order_by('-id')
        if len(all_subscriptions) != 0:
            return all_subscriptions[0].subscription
        return None


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
