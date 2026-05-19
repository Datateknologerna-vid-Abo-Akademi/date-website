from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class FunctionaryRole(models.Model):  # type: ignore[django-manager-missing]
    title = models.CharField(_("Titel"), max_length=200)
    board = models.BooleanField(_("Styrelse"), default=False)

    class Meta:
        verbose_name = _("Funktionärspost")
        verbose_name_plural = _("Funktionärsposter")

    def __str__(self):
        return self.title


class Functionary(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(_("Namn"), max_length=200, blank=True)
    functionary_role = models.ForeignKey(FunctionaryRole, on_delete=models.CASCADE)
    year = models.IntegerField(_("Årtal"))
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Funktionär")
        verbose_name_plural = _("Funktionärer")

    def __str__(self):
        return f"{self.get_full_name()} {self.functionary_role.title} {self.year}"

    def save(self, *args, **kwargs):
        if self.member and not self.name:
            self.name = self.member.get_full_name().strip() or self.member.username
        super().save(*args, **kwargs)

    def clean(self):
        if not self.member and not self.name:
            raise ValidationError(_("Funktionärer måste ha antingen en kopplad medlem eller ett namn."))

    def get_full_name(self):
        return self.member.get_full_name() if self.member else self.name
