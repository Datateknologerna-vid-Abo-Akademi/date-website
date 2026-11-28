from django.db import models
from django.utils.translation import gettext_lazy as _


class Post(models.Model):
    pseudonym = models.CharField(_('Pseudonym'), max_length=50)
    content = models.TextField(_('Meddelande'), max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pseudonym}: {self.content[:50]}"
