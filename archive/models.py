from __future__ import unicode_literals

import datetime
import os
import shutil
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from .fields import PublicFileField


TYPE_CHOICES = (
    ('Documents', 'Dokument'),
    ('PublicFiles', 'OffentligaFiler')
)


class Collection(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    pub_date = models.DateTimeField(default=datetime.datetime.now, null=True)
    hide_for_gulis = models.BooleanField(_('Göm för gulisar'), default=False)

    class Meta:
        verbose_name = _('Samling')
        verbose_name_plural = _('Samlingar')

    def __str__(self):
        return self.title

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def delete(self, *args, **kwargs):
        dir_location = os.path.join(settings.MEDIA_ROOT, self.title.lower())
        shutil.rmtree(dir_location, ignore_errors=True)
        super(Collection, self).delete(*args, **kwargs)

    def clean(self):
        super().clean()
        if '/' in self.title:
            raise ValidationError({'Namn': "Snedstreck är inte tillåtet."})


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)

    if instance.collection.type == "Documents":
        return "documents/{year}/{collection}/{filename}{extension}".format(
            year=instance.collection.pub_date.strftime("%Y"),
            collection=slugify(instance.collection.title),
            filename=slugify(filename_base),
            extension=filename_ext.lower(),
        )
    return "{year}/{collection}/{filename}{extension}".format(
        year=instance.collection.pub_date.strftime("%Y"),
        collection=slugify(instance.collection.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


def get_collections_of_type(t):
    return Collection.objects.filter(type=t)


class DocumentCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Dokumentarkiv')
        proxy = True

class PublicCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Offentliga Filer')
        proxy = True


class Document(models.Model):
    id = models.AutoField(primary_key=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, verbose_name=_('Samling'))
    title = models.CharField(max_length=250, verbose_name=_('Namn'))
    document = models.FileField(upload_to=upload_to, verbose_name=_('Filnamn'))

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('dokument')  # Verbose plural is same.
        verbose_name_plural = _('dokument')


class PublicFile(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('Galleri'), on_delete=models.CASCADE)
    some_file = PublicFileField(upload_to=upload_to, verbose_name=_('file'))
    
    class Meta:
        verbose_name = _("fil")
        verbose_name_plural = _("filer")

    def __str__(self):
        return self.some_file.name
