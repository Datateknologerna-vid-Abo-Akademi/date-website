import datetime
import os

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "Exams/{year}/{archive}/{filename}{extension}".format(
        year=instance.archive.pub_date.strftime("%Y"),
        archive=slugify(instance.archive.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


class ExamArchive(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    pub_date = models.DateTimeField(default=datetime.datetime.now, null=True)
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


class ExamFile(models.Model):
    id = models.AutoField(primary_key=True)
    archive = models.ForeignKey(ExamArchive, on_delete=models.CASCADE, verbose_name=_('Samling'))
    title = models.CharField(max_length=250, verbose_name=_('Namn'))
    document = models.FileField(upload_to=upload_to, verbose_name=_('Filnamn'))

    class Meta:
        verbose_name = _('tentamen')
        verbose_name_plural = _('tentamina')

    def __str__(self):
        return self.title
