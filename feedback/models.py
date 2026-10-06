from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Seeded only into the Swedish column by FeedbackFormSettings.get_solo() - the
# other language columns are left at the field's own default ('') so
# modeltranslation's fallback (MODELTRANSLATION_FALLBACK_LANGUAGES, unset here
# so it defaults to the source language, sv) kicks in for them instead of the
# admin's English/Finnish tabs opening pre-filled with Swedish text that reads
# as already translated. get_solo() creates that one row when the table is
# empty and otherwise returns the lowest-pk row; it does not pin a pk.
DEFAULT_INTRO_TEXT = 'Har du synpunkter eller feedback? Skriv gärna till oss här.'


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
        # Never return the message: Django stores str(obj) in
        # django_admin_log.object_repr, and the admin log is readable by
        # staff who are outside the feedback recipient list. Use
        # FeedbackSubmissionAdmin.message_preview as the authorised read path.
        return f'Inskickad feedback #{self.pk}'


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
    mirrors exambank.ExamBankAccessSettings's get_solo() pattern.

    The site reads one row: the lowest pk. get_solo() returns that row and
    creates it when the table is empty, and FeedbackFormSettingsAdmin pins
    its changelist to the same row, so the editable row and the read row
    cannot diverge. See docs/dev/feedback.md."""

    intro_text = models.CharField(
        _('Introduktionstext'),
        max_length=500,
        blank=True,
        default='',
        help_text=_('Texten som visas ovanför formuläret på /forms/.'),
    )

    class Meta:
        verbose_name = _('Formulärtext')
        verbose_name_plural = _('Formulärtext')

    def __str__(self):
        return str(_('Formulärtext'))

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by('pk').first()
        if obj is None:
            obj = cls.objects.create(intro_text_sv=DEFAULT_INTRO_TEXT)
        return obj
