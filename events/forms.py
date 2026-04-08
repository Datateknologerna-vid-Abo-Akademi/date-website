import logging
import re

from django import forms
from django.contrib.admin import widgets
from django.utils.timezone import now
from django.conf import settings

from date.functions import slugify_max
from events import models
from events.models import Event

logger = logging.getLogger('date')

slug_transtable = str.maketrans("åäö ", "aao_")


def _slug_base_from_title(title):
    base_slug = (title or "").lower().translate(slug_transtable)
    base_slug = re.sub("[^a-zA-Z0-9_]*", '', base_slug)
    return re.sub("__+", '_', base_slug).strip('_')


def _slug_with_suffix(base_slug, suffix):
    suffix_text = "_" + str(suffix)
    base_max_length = models.POST_SLUG_MAX_LENGTH - len(suffix_text)
    return base_slug[:base_max_length].rstrip('_') + suffix_text


def unique_event_slug(slug, title, instance=None):
    slug = (slug or "").strip()
    if slug == "":
        slug = _slug_base_from_title(title)

    slug = slugify_max(slug, max_length=models.POST_SLUG_MAX_LENGTH) or "event"
    base_slug = slug

    collisions = Event.objects.filter(slug=slug)
    if instance and instance.pk:
        collisions = collisions.exclude(pk=instance.pk)

    suffix = 1
    while collisions.exists():
        slug = _slug_with_suffix(base_slug, suffix)
        collisions = Event.objects.filter(slug=slug)
        if instance and instance.pk:
            collisions = collisions.exclude(pk=instance.pk)
        suffix += 1

    return slug


class EventCreationForm(forms.ModelForm):
    user = None
    event_date_start = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    event_date_end = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    sign_up_others = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    sign_up_members = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    sign_up_deadline = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    sign_up_cancelling_deadline = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    parent = forms.ModelChoiceField(queryset=Event.objects.filter(event_date_end__gte=now()), required=False)

    class Meta:
        model = Event
        temp_fields = (
            'title',
            'event_date_start',
            'event_date_end',
            'content',
            'sign_up',
            'sign_up_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'published',
            'sign_up_avec',
            'slug',
            'members_only',
            'passcode',
            'captcha',
            'redirect_link',
            'parent',
        )
        if settings.USE_S3:
            fields = temp_fields + ('s3_image',)
        else:
            fields = temp_fields + ('image',)

    def clean_slug(self):
        return unique_event_slug(
            self.cleaned_data.get('slug'),
            self.cleaned_data.get('title'),
            self.instance,
        )

    def save(self, commit=True):
        post = super(EventCreationForm, self).save(commit=False)

        if self.user is None:
            return None
        post.author = self.user

        if post.published:
            post.published_time = now()

        if not post.sign_up:
            post.sign_up_max_participants = 0
            post.sign_up_others = None
            post.sign_up_members = None
            post.sign_up_deadline = None
            post.sign_up_cancelling = False
            post.sign_up_cancelling_deadline = None

        if commit:
            post.update_or_create(pk=post.pk)
        return post


class EventEditForm(forms.ModelForm):

    user = None

    event_date_start = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())
    event_date_end = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime(), initial=now())

    sign_up_args = {
        "widget": widgets.AdminSplitDateTime(),
        "initial": now(),
        "required": False
    }
    sign_up_others = forms.SplitDateTimeField(**sign_up_args)
    sign_up_members = forms.SplitDateTimeField(**sign_up_args)
    sign_up_deadline = forms.SplitDateTimeField(**sign_up_args)
    sign_up_cancelling_deadline = forms.SplitDateTimeField(**sign_up_args)
    parent = forms.ModelChoiceField(queryset=Event.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # exclude the current instance from parent choices so an event cannot be its own parent
        try:
            if getattr(self, 'instance', None) and getattr(self.instance, 'pk', None):
                # limit parent choices to future events and exclude self
                self.fields['parent'].queryset = Event.objects.filter(
                    event_date_end__gte=now()
                ).exclude(pk=self.instance.pk)
            else:
                # creation: only future events
                self.fields['parent'].queryset = Event.objects.filter(
                    event_date_end__gte=now()
                )
        except Exception:
            # defensive: if fields not yet set or parent missing, ignore
            pass

    class Meta:
        model = Event
        temp_fields = (
            'title',
            'event_date_start',
            'event_date_end',
            'content',
            'sign_up',
            'sign_up_max_participants',
            'sign_up_others',
            'sign_up_members',
            'sign_up_deadline',
            'sign_up_cancelling',
            'sign_up_cancelling_deadline',
            'published',
            'sign_up_avec',
            'slug',
            'members_only',
            'passcode',
            'captcha',
            'redirect_link',
            'parent',
        )
        if settings.USE_S3:
            fields = temp_fields + ('s3_image',)
        else:
            fields = temp_fields + ('image',)

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or "").strip()
        if slug == "" and self.instance and self.instance.slug:
            return self.instance.slug
        return unique_event_slug(slug, self.cleaned_data.get('title'), self.instance)

    def save(self, commit=True):
        post = super(EventEditForm, self).save(commit=False)

        if self.user is None:
            return None

        post.modified_time = now()

        if not post.sign_up:
            post.sign_up_max_participants = 0
            post.sign_up_others = None
            post.sign_up_members = None
            post.sign_up_deadline = None
            post.sign_up_cancelling = False
            post.sign_up_cancelling_deadline = None

        if commit:
            post.update_or_create(pk=post.pk)
        return post


class PasscodeForm(forms.Form):
    passcode = forms.CharField()
