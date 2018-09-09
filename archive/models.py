from django.db import models
from django.utils.translation import ugettext_lazy as _

# Create your models here.


class AbstractFile(models.Model):
    title = models.CharField(max_length=150)
    pub_date = models.DateTimeField()

    class Meta:
        abstract = True

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def __str__(self):
        return self.title


class File(AbstractFile):

    class Meta:
        verbose_name = _('fil')
        verbose_name_plural = _('filer')


class Picture(AbstractFile):
    file = models.ImageField(upload_to='uploads/images')

    class Meta:
        verbose_name = _('bild')
        verbose_name_plural = _('bilder')
