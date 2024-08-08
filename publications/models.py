from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .fields import PrivateFileField


def upload_to(instance, filename):
    return f'pdfs/{filename}'


class PDFFile(models.Model):
    title = models.CharField(_('Title'), max_length=250)
    file = PrivateFileField(upload_to=upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('PDF File')
        verbose_name_plural = _('PDF Files')

    def __str__(self):
        return self.title

    def get_file_url(self):
        if settings.USE_S3:
            return self.file.url
        else:
            return settings.MEDIA_URL + self.file.name
