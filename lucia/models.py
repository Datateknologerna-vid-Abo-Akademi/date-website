import logging

from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field

logger = logging.getLogger("date")

POST_SLUG_MAX_LENGTH = 50


class CandidateQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published_time__isnull=False, published_time__lte=now())


class Candidate(models.Model):
    img_url = models.URLField(_("Bild URL"), max_length=255, blank=True)
    title = models.CharField(_("Titel"), max_length=255, blank=False)
    content = CKEditor5Field(_("Innehåll"), blank=True)
    published_time = models.DateTimeField(
        _("Publiceras"),
        null=True,
        blank=True,
        default=now,
        help_text=_("Lämna tomt för att dölja kandidaten. Välj en framtida tid för schemalagd publicering."),
    )
    slug = models.SlugField(_("Slug"), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)
    poll_url = models.URLField(_("Poll URL"), max_length=255, blank=False)

    objects = CandidateQuerySet.as_manager()

    class Meta:
        verbose_name = _("Lucia")
        verbose_name_plural = _("Lucian")
        ordering = ("id",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("lucia:candidate", args=[self.slug])

    @property
    def published(self):
        return self.published_time is not None and self.published_time <= now()
