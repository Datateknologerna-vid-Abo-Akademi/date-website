from __future__ import unicode_literals
from distutils.command.upload import upload

import logging
import os
from datetime import timedelta

from ckeditor.fields import RichTextField
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Max, JSONField
from django.template.defaulttags import register
from django.utils.timezone import now
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from archive.fields import PublicFileField

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


def upload_to(instance, filename):
    filename_base, filename_ext = os.path.splitext(filename)

    file_location = "events/{filename}{extension}".format(
        filename=slugify(filename_base),
        extension=filename_ext.lower(),
    )
    return file_location


class Event(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    event_date_start = models.DateTimeField(_('Startdatum'), default=now)
    event_date_end = models.DateTimeField(_('Slutdatum'), default=now)
    sign_up_max_participants = models.IntegerField(_('Maximal antal deltagare'),
                                                   choices=[(0, u"Ingen begränsning")] + list(
                                                       zip(range(1, 200), range(1, 200))), default=0)
    sign_up = models.BooleanField(_('Anmälning'), default=True)
    sign_up_members = models.DateTimeField(_('Anmälan öppnas (medlemmar)'), null=True, blank=True, default=now)
    sign_up_others = models.DateTimeField(_('Anmälan öppnas (övriga)'), null=True, blank=True, default=now)
    sign_up_deadline = models.DateTimeField(_('Anmälningen stängs'), null=True, blank=True, default=now)
    sign_up_cancelling = models.BooleanField(_('Avanmälning'), default=True)
    sign_up_cancelling_deadline = models.DateTimeField(_('Avanmälningen stängs'), null=True, blank=True, default=now)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH, blank=True)
    sign_up_avec = models.BooleanField(_('Avec'), default=False)
    members_only = models.BooleanField(_('Kräv inloggning för innehåll'), default=False)
    passcode = models.CharField(_('Passcode'), max_length=255, blank=True)
    image = models.ImageField(_('Bakgrundsbild'), null=True, blank=True, upload_to=upload_to)
    s3_image = PublicFileField(verbose_name=_('Bakgrundsbild'), null=True, blank=True, upload_to=upload_to)

    class Meta:
        verbose_name = _('evenemang')
        verbose_name_plural = _('evenemang')
        ordering = ('id',)

    def __str__(self):
        return self.title

    def event_date_start_pretty(self):
        return self.event_date_start.strftime("%-d %B")

    def publish(self):
        self.published_time = now()
        self.published = True
        self.save()

    def unpublish(self):
        self.published = False
        self.save()

    def update(self):
        self.modified_time = now()
        self.save()

    def get_registrations(self):
        return EventAttendees.objects.filter(event=self).order_by('attendee_nr')

    def get_highest_attendee_nr(self):
        return EventAttendees.objects.filter(event=self).aggregate(Max('attendee_nr'))

    def add_event_attendance(self, user, email, anonymous, preferences, avec_for=None):
        if self.sign_up:
            try:
                registration = EventAttendees.objects.get(email=email, event=self)
            except ObjectDoesNotExist:
                user_pref = {}
                if self.get_registration_form():
                    for item in self.get_registration_form():
                        user_pref[str(item)] = preferences.get(str(item))
                registration = EventAttendees.objects.create(user=user,
                                                                event=self, email=email,
                                                                time_registered=now(), preferences=user_pref,
                                                                anonymous=anonymous, avec_for=avec_for)
                return registration

    def cancel_event_attendance(self, user):
        if self.sign_up:
            registration = EventAttendees.objects.get(user=user, event=self)
            registration.delete()

    def registration_is_open_members(self):
        if self.sign_up_members is None:
            return False
        return now() >= self.sign_up_members and not self.registation_past_due()

    def registration_is_open_others(self):
        if self.sign_up_others is None:
            return False
        return now() >= self.sign_up_others and not self.registation_past_due()

    def registation_past_due(self):
        if self.sign_up_deadline is None:
            return False
        return now() > self.sign_up_deadline

    def event_is_full(self):
        if self.sign_up_max_participants == 0:
            return False
        return EventAttendees.objects.filter(event=self).count() >= self.sign_up_max_participants

    def get_registration_form(self):
        if EventRegistrationForm.objects.filter(event=self).count() == 0:
            return None
        return EventRegistrationForm.objects.filter(event=self).order_by('-id')

    def get_registration_form_public_info(self):
        return EventRegistrationForm.objects.filter(event=self, public_info=True)

    def make_registration_form(self, data=None):
        if self.sign_up:
            fields = {'user': forms.CharField(label='Namn', max_length=255),
                      'email': forms.EmailField(label='Email', validators=[self.validate_unique_email]),
                      'anonymous': forms.BooleanField(label='Anonymt', required=False)}
            if self.get_registration_form():
                for question in reversed(self.get_registration_form()):
                    if question.type == "select":
                        choices = question.choice_list.split(',')
                        fields[question.name] = forms.ChoiceField(label=question.name,
                                                                  choices=list(map(list, zip(choices, choices))),
                                                                  required=question.required)
                    elif question.type == "checkbox":
                        fields[question.name] = forms.BooleanField(label=question.name, required=question.required)
                    elif question.type == "text":
                        fields[question.name] = forms.CharField(label=question.name, required=question.required)
            if self.sign_up_avec:
                fields['avec'] = forms.BooleanField(label='Avec', required=False)
                fields['avec_user'] = forms.CharField(label='Namn', max_length=255, required=False, widget=forms.TextInput(attrs={'class': "avec-field"}))
                fields['avec_email'] = forms.EmailField(label='Email', validators=[self.validate_unique_email], required=False, widget=forms.TextInput(attrs={'class': "avec-field"}))
                fields['avec_anonymous'] = forms.BooleanField(label='Anonymt', required=False, widget=forms.CheckboxInput(attrs={'class': "avec-field"}))
                if self.get_registration_form():
                    for question in reversed(self.get_registration_form()):
                        if not question.hide_for_avec:
                            if question.type == "select":
                                choices = question.choice_list.split(',')
                                fields['avec_'+question.name] = forms.ChoiceField(label=question.name,
                                                                    choices=list(map(list, zip(choices, choices))),
                                                                    required=False, widget=forms.Select(attrs={'class': "avec-field"}))
                            elif question.type == "checkbox":
                                fields['avec_'+question.name] = forms.BooleanField(label=question.name, required=False, widget=forms.CheckboxInput(attrs={'class': "avec-field"}))
                            elif question.type == "text":
                                fields['avec_'+question.name] = forms.CharField(label=question.name, required=False, widget=forms.TextInput(attrs={'class': "avec-field"}))
            return type('EventAttendeeForm', (forms.BaseForm,), {'base_fields': fields, 'data': data}, )

    @register.filter
    def show_attendee_list(self):
        return self.event_date_end > now() + timedelta(-1)

    def validate_unique_email(self, email):
        attendees = self.get_registrations()
        for attendee in attendees:
            if email == attendee.email:
                logger.debug("SAME EMAIL")
                raise ValidationError(_("Det finns redan någon anmäld med denna email"))

class EventRegistrationForm(models.Model):
    event = models.ForeignKey(Event, verbose_name='Event', on_delete=models.CASCADE)
    name = models.CharField(_('Namn'), max_length=255, blank=True)
    type = models.CharField(_('Typ'),
                            choices=(("text", "Text"), ("select", "Multiple choice"), ("checkbox", "Kryssryta")),
                            blank=True, max_length=255, null=True)
    required = models.BooleanField(_('Krävd'), default=False)
    public_info = models.BooleanField(_('Öppen info'), default=False)
    choice_list = models.CharField(_('Alternativ'), max_length=255, blank=True)
    hide_for_avec = models.BooleanField(_('Göm för avec'), default=False)

    class Meta:
        verbose_name = _('Anmälningsfält')
        verbose_name_plural = _('Anmälningsfält')

    def __str__(self):
        return str(self.name)

    def get_choices(self):
        return str(self.choice_list).split(',')


class EventAttendees(models.Model):
    event = models.ForeignKey(Event, verbose_name='Event', on_delete=models.CASCADE)
    attendee_nr = models.PositiveSmallIntegerField(_('#'))
    user = models.CharField(_('Namn'), blank=False, max_length=255)
    email = models.EmailField(_('E-postadress'), blank=False, null=True, unique=False)
    preferences = JSONField(_('Svar'), default=list, blank=True)
    anonymous = models.BooleanField(_('Anonymt'), default=False)
    time_registered = models.DateTimeField(_('Registrerad'))
    avec_for = models.ForeignKey("self", verbose_name=_('Avec till'), null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _('deltagare')
        verbose_name_plural = _('deltagare')
        ordering = ['time_registered', ]
        unique_together = ('event', 'email')

    def __str__(self):
        return str(self.user)

    @register.filter
    def get_preference(self, key):
        return self.preferences.get(str(key), "")

    def save(self, *args, **kwargs):
        if self.attendee_nr is None:
            # attendee_nr increments by 10, e.g 10,20,30,40...
            # this is needed so the admin sorting library will work.
            self.attendee_nr = (self.event.get_registrations().count()+1) * 10
            # Add ten from highest attendee_nr so signups dont get in weird order after deletions.
            if self.event.get_highest_attendee_nr().get('attendee_nr__max'):
                 self.attendee_nr = self.event.get_highest_attendee_nr().get('attendee_nr__max') + 10
        if self.time_registered is None:
            self.time_registered = now()
        if isinstance(self.preferences, list):
            self.preferences = {}
        super(EventAttendees, self).save(*args, **kwargs)
