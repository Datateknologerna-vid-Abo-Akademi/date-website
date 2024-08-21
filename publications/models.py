import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.conf import settings
from publications.fields import PublicFileField


def upload_to(instance, filename):
    return f'pdfs/{instance.slug}/{filename}'

class PDFFile(models.Model):
    title = models.CharField(_('Title'), max_length=250)
    slug = models.SlugField(_('Slug'), max_length=255, unique=True, blank=True,
                            help_text=_('Leave empty to auto-generate from title'))
    file = PublicFileField(_('File'), upload_to=upload_to)
    description = models.TextField(_('Description'), blank=True)
    uploaded_at = models.DateTimeField(_('Uploaded at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    author = models.CharField(_('Author'), max_length=250, blank=True)
    publication_date = models.DateField(_('Publication Date'), null=True, blank=True)
    file_size = models.PositiveIntegerField(_('File Size (bytes)'), editable=False, null=True)
    is_public = models.BooleanField(_('Public Access'), default=False,
                                    help_text=_('If checked, this PDF will be visible to everyone.'
                                                ' If unchecked, it will be hidden from all users.'))
    requires_login = models.BooleanField(_('Requires Login'), default=True,
                                         help_text=_('If checked, users must be logged in to access this PDF'))

    class Meta:
        verbose_name = _('PDF File')
        verbose_name_plural = _('PDF Files')
        ordering = ['-uploaded_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()

        if self.file:
            self.file_size = self.file.size

        super().save(*args, **kwargs)

    def generate_unique_slug(self):
        base_slug = slugify(self.title)
        unique_slug = base_slug
        num = 1
        while PDFFile.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{base_slug}-{num}"
            num += 1
        return unique_slug

    def get_file_url(self):
        return self.file.url

    def delete(self, *args, **kwargs):
        if not settings.USE_S3:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)
