import logging
from django import forms
from django.utils import timezone

from core.functions import slugify_max
from events import models
from events.models import Event

logger = logging.getLogger('date')


class EventCreationForm(forms.ModelForm):

    user = None

    class Meta:
        model = Event
        fields = (
            'title',
            'event_date_start',
            'event_date_end',
            'content',
            'published',
            'sign_up',
            'event_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'slug'
        )

    def save(self, commit=True):
        post = super(EventCreationForm, self).save(commit=False)

        if self.user is None:
            return None
        post.author = self.user

        # Generate slug
        post.slug = slugify_max(self.data['slug'], max_length=models.POST_SLUG_MAX_LENGTH)

        if post.published:
            post.published_time = timezone.now()

        if commit:
            post.save()
        return post


class EventEditForm(forms.ModelForm):

    user = None

    class Meta:
        model = Event
        fields = (
            'title',
            'event_date_start',
            'event_date_end',
            'content',
            'published',
            'sign_up',
            'event_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'slug'
        )

    def save(self, commit=True):
        post = super(EventEditForm, self).save(commit=False)
        if self.user is None:
            return None

        post.modified_time = timezone.now()

        if commit:
            post.save()
        return post
