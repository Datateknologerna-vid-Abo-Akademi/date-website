import logging

from django import forms
from django.utils import timezone

from date.functions import slugify_max
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
            'sign_up_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'slug'
        )

    class Media:
        js = ('js/eventform.js',)

    def save(self, commit=True):
        post = super(EventCreationForm, self).save(commit=False)

        if self.user is None:
            return None
        post.author = self.user

        # Generate slug
        post.slug = slugify_max(self.data['slug'], max_length=models.POST_SLUG_MAX_LENGTH)

        if post.published:
            post.published_time = timezone.now()

        if not post.sign_up:
            post.sign_up_max_participants = 0
            post.sign_up_others = None
            post.sign_up_members = None
            post.sign_up_deadline = None
            post.sign_up_cancelling = False
            post.sign_up_cancelling_deadline = None

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
            'sign_up_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'slug'
        )

    class Media:
        js = ('js/eventform.js',)

    def save(self, commit=True):
        post = super(EventEditForm, self).save(commit=False)
        if self.user is None:
            return None

        post.modified_time = timezone.now()

        if not post.sign_up:
            post.sign_up_max_participants = 0
            post.sign_up_others = None
            post.sign_up_members = None
            post.sign_up_deadline = None
            post.sign_up_cancelling = False
            post.sign_up_cancelling_deadline = None

        if commit:
            post.save()
        return post
