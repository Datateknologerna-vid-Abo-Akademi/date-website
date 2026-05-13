import os

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "{year}/{archive}/{filename}{extension}".format(
        year=instance.archive.pub_date.strftime("%Y"),
        archive=slugify(instance.archive.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


class ExamArchive(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    pub_date = models.DateTimeField(default=timezone.now, null=True)
    hide_for_gulis = models.BooleanField(_('Göm för gulisar'), default=False)

    class Meta:
        verbose_name_plural = verbose_name = _('Tentarkiv')
        ordering = ('title',)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('archive:exams_detail', args=[self.pk])

    def clean(self):
        super().clean()
        if '/' in self.title:
            raise ValidationError({'title': "Snedstreck är inte tillåtet."})


class ExamBankAccessSettings(models.Model):
    require_sign_in = models.BooleanField(
        _('Kräv inloggning'),
        default=True,
        help_text=_('När detta är aktivt kräver tentarkivet vanlig medlemsinloggning.'),
    )
    password_hash = models.CharField(
        _('Lösenord'),
        max_length=128,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = _('Åtkomst till tentarkiv')
        verbose_name_plural = _('Åtkomst till tentarkiv')

    def __str__(self):
        return str(_('Åtkomst till tentarkiv'))

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @property
    def has_password(self):
        return bool(self.password_hash)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password) if raw_password else ''

    def check_password(self, raw_password):
        return bool(self.password_hash) and check_password(raw_password, self.password_hash)


class ExamFile(models.Model):
    id = models.AutoField(primary_key=True)
    archive = models.ForeignKey(ExamArchive, on_delete=models.CASCADE, verbose_name=_('Samling'))
    title = models.CharField(max_length=250, verbose_name=_('Namn'))
    document = models.FileField(upload_to=upload_to, verbose_name=_('Filnamn'))

    class Meta:
        verbose_name = _('tentamen')
        verbose_name_plural = _('tentamina')
        ordering = ('title', 'id')

    def __str__(self):
        return self.title
