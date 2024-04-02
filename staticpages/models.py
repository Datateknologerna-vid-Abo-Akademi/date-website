import logging

from django_ckeditor_5.fields import CKEditor5Field
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


class StaticPageNav(models.Model):
    category_name = models.CharField(_('Kategori'), max_length=255, blank=False)
    nav_element = models.IntegerField(default=0)

    def __str__(self):
        return self.category_name


class StaticPage(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = CKEditor5Field(_('Innehåll'), blank=True)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)
    members_only = models.BooleanField(_('Kräv inloggning'), default=False)

    def __str__(self):
        return self.title

    def update(self):
        self.modified_time = timezone.now()
        self.save()


class StaticUrl(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    url = models.CharField(_('Url'), max_length=200)
    category = models.ForeignKey(StaticPageNav, on_delete=models.CASCADE, blank=True)
    dropdown_element = models.PositiveSmallIntegerField(_('#'), blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.dropdown_element is None:
            max_number = StaticPageNav.objects.filter(category_name=self.category).aggregate(models.Max('dropdown_element'))['dropdown_element__max']
            if max_number is not None:
                self.dropdown_element = max_number + 10
            else:
                self.dropdown_element = 10
        super(StaticUrl, self).save(*args, **kwargs)
