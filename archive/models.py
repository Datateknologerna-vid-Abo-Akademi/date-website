from __future__ import unicode_literals
import os

from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
import datetime


TYPE_CHOICES = (
    ('Pictures', 'pictures'),
    ('Documents', 'documents'),
)


class Collection(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    type = models.CharField(max_length=2, choices=TYPE_CHOICES)
    pub_date = models.DateTimeField(default=datetime.datetime.now, null=True)

    class Meta:
        verbose_name = _('Samling')
        verbose_name_plural = _('Samlingar')


    def get_absolute_url(self):
        return reverse('archive:detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.title

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "{collection}/{filename}{extension}".format(
        collection=slugify(instance.collection.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


class Picture(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('Galleri'), on_delete=models.CASCADE)
    image = models.ImageField(upload_to=upload_to)
    favorite = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("bild")
        verbose_name_plural = _("bilder")

    def __str__(self):
        return self.image.name


class Document(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('samling'), on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    document = models.FileField(upload_to=upload_to)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('dokument')  # Verbose plural is same.
