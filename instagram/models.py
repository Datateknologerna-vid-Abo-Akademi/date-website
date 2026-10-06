import re

from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import validate_image_file_extension
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.fields import PublicFileField

POST_LINK = re.compile(r'instagram\.com/(?:[^/?#]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)', re.IGNORECASE)

# The slider shows posts 150px tall; high-density screens need twice that to stay sharp.
MIN_IMAGE_HEIGHT = 300


def validate_image_height(file):
    # A raw upload has no _committed attribute yet, so it must be treated as new.
    if not isinstance(file, UploadedFile) and getattr(file, '_committed', True):
        return
    _width, height = get_image_dimensions(file)
    if height is None:
        raise ValidationError(_('Filen är inte en bild.'))
    if height < MIN_IMAGE_HEIGHT:
        raise ValidationError(
            _('Bilden är för liten (%(height)s px hög). Ladda upp en bild som är minst %(minimum)s px hög.'),
            params={'height': height, 'minimum': MIN_IMAGE_HEIGHT},
        )


class IgUrl(models.Model):
    image = PublicFileField(
        _('Bild'),
        upload_to='instagram/',
        blank=True,
        validators=[validate_image_file_extension, validate_image_height],
    )
    url = models.CharField(
        _('URL'),
        max_length=255,
        blank=True,
        help_text=_('Fylls i av Instagram-uppdateraren. Lämna tomt när du laddar upp en bild.'),
    )
    shortcode = models.CharField(
        _('Instagram-inlägg'),
        max_length=255,
        help_text=_('Klistra in länken till inlägget, t.ex. https://www.instagram.com/p/ABC123/.'),
    )

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return self.shortcode

    @property
    def image_url(self):
        return self.image.url if self.image else self.url

    def clean(self):
        match = POST_LINK.search(self.shortcode)
        if match:
            self.shortcode = match.group(1)
        if not self.image and not self.url:
            raise ValidationError({'image': _('Ladda upp en bild för inlägget.')})
