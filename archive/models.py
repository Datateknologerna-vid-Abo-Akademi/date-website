from __future__ import unicode_literals

import datetime
import os
import shutil
import sys
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.template.defaulttags import register
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from PIL import Image
from .fields import PublicFileField
from django.core.exceptions import ValidationError


TYPE_CHOICES = (
    ('Pictures', 'Bilder'),
    ('Documents', 'Dokument'),
    ('Exams', 'Tenter'),
    ('PublicFiles', 'OffentligaFiler')
)


class Collection(models.Model):
    title = models.CharField(_('Namn'), max_length=250)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    pub_date = models.DateTimeField(default=datetime.datetime.now, null=True)
    hide_for_gulis = models.BooleanField(_('Göm för gulisar'), default=False)

    class Meta:
        verbose_name = _('Samling')
        verbose_name_plural = _('Samlingar')

    def get_first_picture(self):
        if self.type == 'Pictures':
            return self.picture_set.first()

    def get_absolute_url(self):
        return reverse('archive:detail', kwargs={'album': self.title, 'year': self.pub_date.year})

    def __str__(self):
        return self.title

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def delete(self, *args, **kwargs):
        dir_location = os.path.join(settings.MEDIA_ROOT, self.title.lower())
        shutil.rmtree(dir_location, ignore_errors=True)
        super(Collection, self).delete(*args, **kwargs)

    def clean(self):
        super().clean()
        if '/' in self.title:
            raise ValidationError({'Namn': "Snedstreck är inte tillåtet."})

    @register.filter
    def get_file_count(self):
        return Picture.objects.filter(collection=self).count()


def upload_to(instance, filename):
    file_location = ""
    filename_base, filename_ext = os.path.splitext(filename)

    if instance.collection.type == "Documents":
        file_location = "documents/{year}/{collection}/{filename}{extension}".format(
            year=instance.collection.pub_date.strftime("%Y"),
            collection=slugify(instance.collection.title),
            filename=slugify(filename_base),
            extension=filename_ext.lower(),
        )
    
    elif instance.collection.type == "Exams":
        file_location = "Exams/{year}/{collection}/{filename}{extension}".format(
            year=instance.collection.pub_date.strftime("%Y"),
            collection=slugify(instance.collection.title),
            filename=slugify(filename_base),
            extension=filename_ext.lower(),
        )

    else:
        file_location = "{year}/{collection}/{filename}{extension}".format(
            year=instance.collection.pub_date.strftime("%Y"),
            collection=slugify(instance.collection.title),
            filename=slugify(filename_base),
            extension=filename_ext.lower(),
        )
    return file_location


def get_collections_of_type(t):
    return Collection.objects.filter(type=t)


def compress_image(uploaded_image):
    basewidth = 1600
    img = Image.open(uploaded_image)
    outputIOStream = BytesIO()
    img = img.convert('RGB')
    wpercent = (basewidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((basewidth, hsize), Image.LANCZOS)

    img.save(outputIOStream, format='JPEG', quality=60)
    outputIOStream.seek(0)
    uploaded_image = InMemoryUploadedFile(outputIOStream, 'ImageField', "%s.jpg" % uploaded_image.name.split('.')[0],  'image/jpeg', sys.getsizeof(outputIOStream), None)
    return uploaded_image


class PictureCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Bildarkiv')
        proxy = True


class DocumentCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Dokumentarkiv')
        proxy = True

class ExamCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Tentarkiv')
        proxy = True

class PublicCollection(Collection):
    class Meta:
        verbose_name_plural = verbose_name = _('Offentliga Filer')
        proxy = True


class Picture(models.Model):
    UPLOAD_PROVIDER_LOCAL = "local"
    UPLOAD_PROVIDER_CLOUDFLARE = "cloudflare"
    UPLOAD_PROVIDER_CHOICES = (
        (UPLOAD_PROVIDER_LOCAL, "Local"),
        (UPLOAD_PROVIDER_CLOUDFLARE, "Cloudflare"),
    )

    collection = models.ForeignKey(Collection, verbose_name=_('Galleri'), on_delete=models.CASCADE)
    image = models.ImageField(upload_to=upload_to, null=True, blank=True)
    favorite = models.BooleanField(default=False)
    cloudflare_image_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    cloudflare_variant_url = models.URLField(max_length=500, null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    upload_provider = models.CharField(
        max_length=32,
        choices=UPLOAD_PROVIDER_CHOICES,
        default=UPLOAD_PROVIDER_LOCAL,
    )

    class Meta:
        verbose_name = _("bild")
        verbose_name_plural = _("bilder")

    def __str__(self):
        return self.original_filename or self.cloudflare_image_id or getattr(self.image, 'name', '')

    @property
    def image_url(self):
        if self.upload_provider == self.UPLOAD_PROVIDER_CLOUDFLARE and self.cloudflare_variant_url:
            return self.cloudflare_variant_url
        if self.image:
            return self.image.url
        return ""

    def get_file_path(self):
        return self.image_url

    def save(self, *args, **kwargs):
        if (
            not self.id
            and self.upload_provider == self.UPLOAD_PROVIDER_LOCAL
            and self.image
            and not getattr(self, "_skip_compression", False)
        ):
            self.image = compress_image(self.image)
        super(Picture, self).save(*args, **kwargs)
    
    if not settings.USE_S3:
        def delete(self, using=None, keep_parents=False):
                if self.image:
                    os.remove(os.path.join(settings.MEDIA_ROOT, self.image.name))
                super(Picture, self).delete(using, keep_parents)


class Document(models.Model):
    id = models.AutoField(primary_key=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, verbose_name=_('Samling'))
    title = models.CharField(max_length=250, verbose_name=_('Namn'))
    document = models.FileField(upload_to=upload_to, verbose_name=_('Filnamn'))

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('dokument')  # Verbose plural is same.
        verbose_name_plural = _('dokument')


class PublicFile(models.Model):
    collection = models.ForeignKey(Collection, verbose_name=_('Galleri'), on_delete=models.CASCADE)
    some_file = PublicFileField(upload_to=upload_to, verbose_name=_('file'))
    
    class Meta:
        verbose_name = _("fil")
        verbose_name_plural = _("filer")

    def __str__(self):
        return self.some_file.name
