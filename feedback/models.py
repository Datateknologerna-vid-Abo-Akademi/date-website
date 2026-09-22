from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FeedbackSubmission(models.Model):
    """One submitted response to the site's single feedback form at
    /forms/. Fixed shape, mirrors harassment.Harassment exactly - there is
    only ever one feedback form, not a per-form slug system."""

    email = models.EmailField(_('Email'), max_length=255, blank=True, null=True)  # noqa: DJ001
    message = models.TextField(_('Meddelande'), max_length=1500)
    created_time = models.DateTimeField(_('Skickad'), default=timezone.now)

    class Meta:
        verbose_name = _('Inskickad feedback')
        verbose_name_plural = _('Inskickad feedback')
        ordering = ('-created_time',)

    def __str__(self):
        return self.message


class FeedbackEmailRecipient(models.Model):
    """Notification recipients for the feedback form - mirrors
    harassment.HarassmentEmailRecipient exactly."""

    recipient_email = models.EmailField(_('Email'), max_length=320)

    class Meta:
        verbose_name = _('Mottagare för feedback')
        verbose_name_plural = _('Mottagare för feedback')

    def __str__(self):
        return self.recipient_email


class FeedbackFormSettings(models.Model):
    """Singleton row holding the admin-editable copy shown on /forms/ -
    mirrors exambank.ExamBankAccessSettings's get_solo() pattern. There is
    only ever one row (pk=1); see docs/dev/feedback.md."""

    intro_text = models.CharField(
        _('Introduktionstext'),
        max_length=500,
        default='Har du synpunkter eller feedback? Skriv gärna till oss här.',
        help_text=_('Texten som visas ovanför formuläret på /forms/.'),
    )

    class Meta:
        verbose_name = _('Formulärtext')
        verbose_name_plural = _('Formulärtext')

    def __str__(self):
        return str(_('Formulärtext'))

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj
