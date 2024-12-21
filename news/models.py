import logging

from django_ckeditor_5.fields import CKEditor5Field
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


class Category(models.Model):
    name = models.CharField(_('Namn'), max_length=255, blank=False)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False)

    class Meta:
        verbose_name = _('kategori')
        verbose_name_plural = _('kategorier')
        ordering = ('name',)

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_('Kategori'), blank=True, null=True)
    content = CKEditor5Field(_('Innehåll'), blank=True)
    author = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    class Meta:
        verbose_name = _('nyhet')
        verbose_name_plural = _('nyheter')
        ordering = ('id',)

    def __str__(self):
        return self.title

    def publish(self):
        self.published_time = timezone.now()
        self.published = True
        self.save()

    def unpublish(self):
        self.published = False
        self.save()

    def update(self):
        self.modified_time = timezone.now()
        self.save()
