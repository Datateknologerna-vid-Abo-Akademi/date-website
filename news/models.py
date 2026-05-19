import logging

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field

logger = logging.getLogger("date")

POST_SLUG_MAX_LENGTH = 50


class Category(models.Model):  # type: ignore[django-manager-missing]
    name = models.CharField(_("Namn"), max_length=255, blank=False)
    slug = models.SlugField(_("Slug"), unique=True, allow_unicode=False)

    class Meta:
        verbose_name = _("kategori")
        verbose_name_plural = _("kategorier")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("news:aa_index", args=[self.slug])


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published_time__isnull=False, published_time__lte=timezone.now())


class Post(models.Model):
    title = models.CharField(_("Titel"), max_length=255, blank=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_("Kategori"), blank=True, null=True)
    content = CKEditor5Field(_("Innehåll"), blank=True)
    author = models.ForeignKey("members.Member", on_delete=models.CASCADE)
    created_time = models.DateTimeField(_("Skapad"), default=timezone.now)
    published_time = models.DateTimeField(
        _("Publiceras"),
        null=True,
        blank=True,
        default=timezone.now,
        help_text=_("Lämna tomt för att dölja nyheten. Välj en framtida tid för schemalagd publicering."),
    )
    modified_time = models.DateTimeField(_("Modifierad"), editable=False, null=True, blank=True)
    slug = models.SlugField(_("Slug"), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    objects = PostQuerySet.as_manager()  # type: ignore[django-manager-missing]

    class Meta:
        verbose_name = _("nyhet")
        verbose_name_plural = _("nyheter")
        ordering = ("id",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.category_id:
            return reverse("news:detail", args=[self.category.slug, self.slug])
        return reverse("news:detail", args=[self.slug])

    @property
    def published(self):
        return self.published_time is not None and self.published_time <= timezone.now()

    def publish(self):
        self.published_time = timezone.now()
        self.save()

    def unpublish(self):
        self.published_time = None
        self.save()

    def update(self):
        self.modified_time = timezone.now()
        self.save()
