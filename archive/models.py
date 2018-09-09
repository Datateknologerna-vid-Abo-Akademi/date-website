from __future__ import unicode_literals

import os

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify


@python_2_unicode_compatible
class Collection(models.Model):
    title = models.CharField(_('Namn'), max_length=100)
    pub_date = models.DateTimeField()

    class Meta:
        verbose_name =_('Samling')
        verbose_name_plural =_('Samlingar')

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


@python_2_unicode_compatible
class AbstractFile(models.Model):
    """
        abstract class for all fileTypes, defines all common characters.
    """

    collection = models.ForeignKey(Collection, verbose_name=_('Samling'), on_delete=models.CASCADE)
    title = models.CharField(_('Namn'), max_length=100, blank=True)
    file = models.FileField(_('Fil'), blank=True, upload_to=upload_to)

    class Meta:
        verbose_name = _("fil")
        verbose_name_plural = _("filer")

    def __str__(self):
        return self.title
