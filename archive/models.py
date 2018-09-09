from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
import datetime
import os


class Collection(models.Model):
    title = models.CharField(_('title'), max_length=100)
    pub_date = models.DateTimeField(default=datetime.datetime.now())

    class Meta:
        verbose_name =_('Collection')
        verbose_name_plural =_('Collections')

    def __str__(self):
        return self.title


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "collection/{collection}/{filename}{extension}".format(
        collection=slugify(instance.belongs_in.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


class AbstractFile(models.Model):
    """
        abstract class for all fileTypes, defines all common characters.
    """

    belongs_in = models.ForeignKey(Collection, verbose_name=_('Collection'), on_delete=models.CASCADE)
    title = models.CharField(_('Namn'), max_length=100, blank=True)
    pub_date = models.DateTimeField(default=datetime.datetime.now())
    file = models.FileField(_('Fil'), blank=True, upload_to=upload_to)

    class Meta:
        verbose_name = _("fil")
        verbose_name_plural = _("filer")

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def __str__(self):
        return self.title
