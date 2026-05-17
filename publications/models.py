import os

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from publications.fields import PublicFileField


def upload_to(instance, filename):
    return f'pdfs/{instance.slug}/{filename}'


def cover_upload_to(instance, filename):
    return f'publication-covers/{instance.slug}/{filename}'

class PDFFile(models.Model):
    title = models.CharField(_('Title'), max_length=250)
    slug = models.SlugField(_('Slug'), max_length=255, unique=True, blank=True,
                            help_text=_('Leave empty to auto-generate from title'))
    file = PublicFileField(_('File'), upload_to=upload_to, blank=True)
    redirect_url = models.URLField(
        _('Redirect URL'),
        max_length=500,
        blank=True,
        help_text=_('If set, visitors are sent to this URL instead of the internal PDF viewer.'),
    )
    cover_image = PublicFileField(
        _('Cover image'),
        upload_to=cover_upload_to,
        blank=True,
        help_text=_('Optional thumbnail image shown on the publications list.'),
    )
    description = models.TextField(_('Description'), blank=True)
    uploaded_at = models.DateTimeField(_('Uploaded at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    publication_date = models.DateField(_('Publication Date'), default=timezone.now, null=True, blank=True)
    is_public = models.BooleanField(_('Public Access'), default=True,
                                    help_text=_('If checked, this PDF will be visible to everyone.'
                                                ' If unchecked, it will be hidden from all users.'))
    requires_login = models.BooleanField(_('Requires Login'), default=False,
                                         help_text=_('If checked, users must be logged in to access this PDF'))

    class Meta:
        verbose_name = _('PDF File')
        verbose_name_plural = _('PDF Files')
        ordering = ['-uploaded_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('publications:pdf_view', args=[self.slug])

    def clean(self):
        super().clean()
        if not self.file and not self.redirect_url:
            raise ValidationError({
                'file': _('Upload a PDF file or set a redirect URL.'),
                'redirect_url': _('Upload a PDF file or set a redirect URL.'),
            })

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
        if not self.file:
            return ''
        return self.file.url

    def get_safe_file_url(self):
        try:
            return self.get_file_url()
        except Exception:
            return ''

    def get_cover_url(self):
        if not self.cover_image:
            return ''
        return self.cover_image.url

    def get_safe_cover_url(self):
        try:
            return self.get_cover_url()
        except Exception:
            return ''

    def get_public_url(self):
        return self.redirect_url or self.get_absolute_url()

    def delete(self, *args, **kwargs):
        if self.file and not settings.USE_S3:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)
