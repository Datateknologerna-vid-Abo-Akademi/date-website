from django.db import models
from django.utils.translation import gettext_lazy as _

from .redaction import report_label


class Harassment(models.Model):
    email = models.EmailField(_('Email'), max_length=255, blank=True, null=True)  # noqa: DJ001
    message = models.TextField(_('Beskrivning av händelsen'), blank=False, max_length=1500)

    def __str__(self):
        # Never return the report: Django stores str(obj) in
        # django_admin_log.object_repr, and the admin log is readable by staff
        # who are outside the report recipient list.
        return report_label(self.pk)


class HarassmentEmailRecipient(models.Model):
    recipient_email = models.EmailField(max_length=320)

    class Meta:
        verbose_name = _("Emailmottagare för Trakasserianmälan")
        verbose_name_plural = _("Emailmottagare för Trakasserianmälan")

    def __str__(self):
        return self.recipient_email
