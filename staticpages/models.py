import logging
import os

from django_ckeditor_5.fields import CKEditor5Field
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.fields import PublicFileField

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50

def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)

    file_location = "pages/{filename}{extension}".format(
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )
    return file_location

class StaticPageNav(models.Model):
    category_name = models.CharField(_('Kategori'), max_length=255, blank=False)
    nav_element = models.IntegerField(default=0)
    use_category_url = models.BooleanField(_('Använd kategorins URL'), default=False)
    url = models.CharField(_('Url'), max_length=200, blank=True)

    def __str__(self):
        return self.category_name


class StaticPage(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = CKEditor5Field(_('Innehåll'), blank=True)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)
    members_only = models.BooleanField(_('Kräv inloggning'), default=False)
    image = models.ImageField(_('Bakgrundsbild'), null=True, blank=True, upload_to=upload_to)
    s3_image = PublicFileField(verbose_name=_('Bakgrundsbild'), null=True, blank=True, upload_to=upload_to)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('staticpages:page', args=[self.slug])

    def clean(self):
        super().clean()
        if self.image and self.s3_image:
            raise ValidationError({
                'image': _('Välj antingen en lokal bakgrundsbild eller en publik S3-bakgrundsbild, inte båda.'),
                's3_image': _('Välj antingen en lokal bakgrundsbild eller en publik S3-bakgrundsbild, inte båda.'),
            })

    @property
    def background_image_url(self):
        field_names = ("s3_image", "image") if settings.USE_S3 else ("image", "s3_image")
        for field_name in field_names:
            field = getattr(self, field_name, None)
            if not field:
                continue
            try:
                return field.url
            except Exception as exc:
                logger.warning(
                    "Unable to resolve %s URL for static page %s (%s): %s",
                    field_name,
                    self.pk,
                    self.slug or self.title,
                    exc,
                )
        return ""

    def update(self):
        self.modified_time = timezone.now()
        self.save()


class StaticUrl(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    url = models.CharField(_('Url'), max_length=200, blank = True)
    category = models.ForeignKey(StaticPageNav, on_delete=models.CASCADE, blank=True)
    dropdown_element = models.PositiveSmallIntegerField(_('#'), blank=True)
    logged_in_only = models.BooleanField(_('Visa endast åt inloggade användare'), default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')

    class Meta:
        ordering = ['dropdown_element']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.parent is not None and not self.category_id:
            self.category = self.parent.category

        if self.dropdown_element is None:
            if self.parent is not None:
                max_number = StaticUrl.objects.filter(parent=self.parent).aggregate(
                    models.Max('dropdown_element')
                )['dropdown_element__max']
            else:
                max_number = StaticUrl.objects.filter(category=self.category, parent=None).aggregate(
                    models.Max('dropdown_element')
                )['dropdown_element__max']
            self.dropdown_element = (max_number + 10) if max_number is not None else 10
        super(StaticUrl, self).save(*args, **kwargs)
