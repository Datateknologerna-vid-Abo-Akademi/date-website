from __future__ import unicode_literals
import os
import sys
from django.conf import settings

from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import shutil

from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
import datetime


TYPE_CHOICES = (
    ('Pictures', 'Bilder'),
    ('Documents', 'Dokument'),
)


class Collection(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    pub_date = models.DateTimeField(default=datetime.datetime.now, null=True)

    class Meta:
        verbose_name = _('Samling')
        verbose_name_plural = _('Samlingar')

    def get_first_picture(self):
        if self.type == 'Pictures':
            return self.picture_set.first()

    def get_absolute_url(self):
        return reverse('archive:detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.title

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def delete(self, *args, **kwargs):
        dir_location = os.path.join(settings.MEDIA_ROOT, self.title.lower())
        print(dir_location)
        shutil.rmtree(dir_location, ignore_errors=True)
        super(Collection, self).delete(*args, **kwargs)


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)
    return "{collection}/{filename}{extension}".format(
        collection=slugify(instance.collection.title),
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )


def compress_image(uploaded_image):
    basewidth = 1600
    img = Image.open(uploaded_image)
    outputIOStream = BytesIO()
    img = img.convert('RGB')
    # img = img.resize((1020, 573))

    wpercent = (basewidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((basewidth, hsize), Image.ANTIALIAS)

    img.save(outputIOStream, format='JPEG', quality=60)
    outputIOStream.seek(0)
    uploaded_image = InMemoryUploadedFile(outputIOStream, 'ImageField', "%s.jpg" % uploaded_image.name.split('.')[0],  'image/jpeg', sys.getsizeof(outputIOStream), None)
    return uploaded_image


class Picture(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('Galleri'), on_delete=models.CASCADE)
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
        super(Picture, self).save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        os.remove(os.path.join(settings.MEDIA_ROOT, self.image.name))
        super(Picture, self).delete(using, keep_parents)


class Document(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('samling'), on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    document = models.FileField(upload_to=upload_to)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('dokument')  # Verbose plural is same.
