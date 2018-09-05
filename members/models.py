import logging

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.utils.translation import ugettext_lazy as _
from django.db import models

from date import settings

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

MEMBERSHP_TYPES = (
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
    membership_type = models.IntegerField(_('Medlemskap'), default=FRESHMAN, choices=MEMBERSHP_TYPES, blank=False)
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

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser
