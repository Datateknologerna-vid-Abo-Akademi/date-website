import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from django.utils import timezone

# Create your models here.

class AlumniEmailRecipient(models.Model):
    recipient_email = models.EmailField(max_length=256)

    def __str__(self):
        return self.recipient_email

    class Meta:
        verbose_name = _("Emailmottagare för ÅAATK")
        verbose_name_plural = _("Emailmottagare för ÅAATK")


class AlumniUpdateToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.token

    class Meta:
        verbose_name = _("Alumni Update Token")
        verbose_name_plural = _("Alumni Update Tokens")

    def is_valid(self):
        """Check if the token is not expired. Tokens are valid for 30 minutes."""
        expiration_time = self.created_at + timezone.timedelta(minutes=30)
        return timezone.now() < expiration_time
