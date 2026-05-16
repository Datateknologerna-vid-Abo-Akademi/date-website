import logging
import os
import sys
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from PIL import Image

logger = logging.getLogger('date')


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "{year}/{album}/{filename}{extension}".format(
        year=instance.album.pub_date.strftime("%Y"),
        album=slugify(instance.album.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


def compress_image(uploaded_image):
    basewidth = 1600
    img = Image.open(uploaded_image)
    output_io_stream = BytesIO()
    img = img.convert('RGB')
    wpercent = basewidth / float(img.size[0])
    hsize = int(float(img.size[1]) * float(wpercent))
    img = img.resize((basewidth, hsize), Image.LANCZOS)
    img.save(output_io_stream, format='JPEG', quality=60)
    output_io_stream.seek(0)
    return InMemoryUploadedFile(
        output_io_stream,
        'ImageField',
        "%s.jpg" % uploaded_image.name.split('.')[0],
        'image/jpeg',
        sys.getsizeof(output_io_stream),
        None,
    )


class Album(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    pub_date = models.DateTimeField(default=timezone.now, null=True)
    hide_for_gulis = models.BooleanField(_('Göm för gulisar'), default=False)
    redirect_url = models.URLField(
        _('Omdirigeringsadress'),
        max_length=500,
        blank=True,
        help_text=_('Om angiven skickas besökaren vidare hit när albumet öppnas.'),
    )
    thumbnail = models.ImageField(
        _('Albumminiatyr'),
        upload_to='archive/thumbnails/',
        blank=True,
        help_text=_('Valfri bild som visas som albumets miniatyr.'),
    )

    class Meta:
        verbose_name_plural = verbose_name = _('Bildarkiv')
        ordering = ('-pub_date',)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('archive:detail', kwargs={'album': self.title, 'year': self.pub_date.year})

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def clean(self):
        super().clean()
        if '/' in self.title:
            raise ValidationError({'title': "Snedstreck är inte tillåtet."})


class Photo(models.Model):
    album = models.ForeignKey(Album, verbose_name=_('Galleri'), on_delete=models.CASCADE)
    image = models.ImageField(upload_to=upload_to)
    favorite = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("bild")
        verbose_name_plural = _("bilder")

    def __str__(self):
        return self.image.name

    def get_file_path(self):
        return self.image.url

    def save(self, *args, **kwargs):
        if not self.id:
            self.image = compress_image(self.image)
        super().save(*args, **kwargs)

    if not settings.USE_S3:
        def delete(self, using=None, keep_parents=False):
            try:
                os.remove(os.path.join(settings.MEDIA_ROOT, self.image.name))
            except FileNotFoundError:
                pass
            super().delete(using, keep_parents)
