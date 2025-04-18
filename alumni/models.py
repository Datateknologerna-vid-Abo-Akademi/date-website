from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class AlumniEmailRecipient(models.Model):
    recipient_email = models.EmailField(max_length=256)

    def __str__(self):
        return self.recipient_email

    class Meta:
        verbose_name = _("Emailmottagare för ÅAATK")
        verbose_name_plural = _("Emailmottagare för ÅAATK")
