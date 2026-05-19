from django.db import models
from django.utils.translation import gettext_lazy as _


class Harassment(models.Model):
    email = models.EmailField(_("Email"), max_length=255, blank=True, null=True)  # noqa: DJ001
    message = models.TextField(_("Beskrivning av händelsen"), blank=False, max_length=1500)

    def __str__(self):
        return self.message


class HarassmentEmailRecipient(models.Model):
    recipient_email = models.EmailField(max_length=320)

    class Meta:
        verbose_name = _("Emailmottagare för Trakasserianmälan")
        verbose_name_plural = _("Emailmottagare för Trakasserianmälan")

    def __str__(self):
        return self.recipient_email
