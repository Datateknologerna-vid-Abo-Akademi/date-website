import os

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.conf import settings
from core.storage_backends import PublicMediaStorage
import pymupdf

def upload_to(instance, filename):
    return f'pdfs/{instance.slug}/{filename}'

class PDFFile(models.Model):
    title = models.CharField(_('Title'), max_length=250)
    slug = models.SlugField(_('Slug'), max_length=255, unique=True, blank=True,
                            help_text=_('Leave empty to auto-generate from title'))
    file = models.FileField(_('File'), upload_to=upload_to, storage=PublicMediaStorage() if settings.USE_S3 else None)
    description = models.TextField(_('Description'), blank=True)
    uploaded_at = models.DateTimeField(_('Uploaded at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    author = models.CharField(_('Author'), max_length=250, blank=True)
    publication_date = models.DateField(_('Publication Date'), null=True, blank=True)
    file_size = models.PositiveIntegerField(_('File Size (bytes)'), editable=False, null=True)
    num_pages = models.PositiveIntegerField(_('Number of Pages'), editable=False, null=True)
    is_public = models.BooleanField(_('Public Access'), default=False, help_text=_('If checked, this PDF will be accessible without login'))

    class Meta:
        verbose_name = _('PDF File')
        verbose_name_plural = _('PDF Files')
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()

        if self.file:
            self.file_size = self.file.size
            self.num_pages = self.count_pdf_pages()


        super().save(*args, **kwargs)

    def count_pdf_pages(self):
        if not os.path.exists(self.file.path):
            return 0
        with pymupdf.open(self.file.path) as pdf:
            return pdf.page_count

    def generate_unique_slug(self):
        base_slug = slugify(self.title)
        unique_slug = base_slug
        num = 1
        while PDFFile.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{base_slug}-{num}"
            num += 1
        return unique_slug

    def get_file_url(self):
        if settings.USE_S3:
            return self.file.url
        return settings.MEDIA_URL + self.file.name