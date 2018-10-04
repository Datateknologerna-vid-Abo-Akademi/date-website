import logging

from ckeditor.fields import RichTextField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from core.functions import days_hence
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.postgres.fields import JSONField

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50

class Event(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    event_date_start = models.DateTimeField(_('Startdatum'), default=timezone.now)
    event_date_end = models.DateTimeField(_('Slutdatum'), default=timezone.now)
    event_max_participants = models.IntegerField(_('Maximal antal deltagare'), choices=[(0, u"Ingen begränsning")] + list(zip(range(1,200), range(1,200))), default=0)
    sign_up = models.BooleanField(_('Anmälning'), default=True)
    sign_up_members = models.DateTimeField(_('Anmälan öppnas (medlemmar)'), null=True, blank=True, default=timezone.now)
    sign_up_others = models.DateTimeField(_('Anmälan öppnas (övriga)'), null=True, blank=True, default=timezone.now)
    sign_up_deadline = models.DateTimeField(_('Anmälningen stängs'), default=days_hence(7))
    sign_up_cancelling = models.BooleanField(_('Avanmälning'), default=True)
    sign_up_cancelling_deadline = models.DateTimeField(_('Avanmälningen stängs'), default=days_hence(5))
    author = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    class Meta:
        verbose_name = _('evenemang')
        verbose_name_plural = _('evenemang')
        ordering = ('id',)

    def __str__(self):
        return self.title

    def publish(self):
        self.published_time = timezone.now()
        self.published = True
        self.save()

    def unpublish(self):
        self.published = False
        self.save()

    def update(self):
        self.modified_time = timezone.now()
        self.save()

    def get_link(self):
        return reverse('events:detail', args=[self.slug])

    def get_registrations(self):
        return EventAttendees.objects.filter(event=self)

    def add_event_attendance(self, user, preferences):
        try:
            registration = EventAttendees.objects.get(user=user, event=self, preferences=preferences)
        except ObjectDoesNotExist:
            registration = EventAttendees.objects.create(user=user,
                                                        event=self,
                                                        time_registered=timezone.now(), preferences=preferences)

    def cancel_event_attendance(self, user):
        registration = EventAttendees.objects.get(user=user, event=self)
        registration.delete()

    def registration_is_open_members(self):
        return timezone.now() >= self.sign_up_members and not self.event_is_full() and not self.registation_past_due()

    def registration_is_open_others(self):
        return timezone.now() >= self.sign_up_others and not self.event_is_full() and not self.registation_past_due()

    def registation_past_due(self):
        return timezone.now() > self.sign_up_deadline

    def event_is_full(self):
        if self.event_max_participants == 0:
            return False
        return EventAttendees.objects.filter(event=self).count() >= self.event_max_participants

    def get_registration_form(self):
        return EventRegistrationForm.objects.filter(event = self)


class EventRegistrationForm(models.Model):
    event = models.ForeignKey(Event, verbose_name='Event', on_delete=models.CASCADE)
    name = models.CharField(_('Namn'), max_length=255, blank=True)
    type = models.CharField(_('Typ'), choices=(("text", "Text"),("select", "Multiple choice"),("checkbox", "Kryssryta")), blank=True, max_length=255, null=True)
    required = models.BooleanField(_('Krävd'), default=False)
    published = models.BooleanField(_('Visa'), default=True)
    choice_list = models.CharField(_('Värden'), max_length=255, blank=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = _('Anmälningsfält')
        verbose_name_plural = _('Anmälningsfält')

    def get_choices(self):
        return str(self.choice_list).split(',')


class EventAttendees(models.Model):
    event = models.ForeignKey(Event, verbose_name='Event', on_delete=models.CASCADE)
    user = models.ForeignKey('members.Member', verbose_name='Deltagare', on_delete=models.CASCADE)
    preferences = JSONField(_('Svar'), default=list)
    time_registered = models.DateTimeField(_('Registrerad'))

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = _('deltagare')
        verbose_name_plural = _('deltagare')
        ordering = ['time_registered', ]
        unique_together = ('event', 'user')

    def save(self, *args, **kwargs):
        if self.time_registered is None:
            self.time_registered = timezone.now()
        super(EventAttendees, self).save(*args, **kwargs)
