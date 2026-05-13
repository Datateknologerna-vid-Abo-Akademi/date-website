import logging

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.admin_widgets import flatpickr_datetime_field

from date.functions import slugify_max
from news import models
from news.models import Post

logger = logging.getLogger('date')


class PostCreationForm(forms.ModelForm):

    user = None
    published_time = flatpickr_datetime_field(initial=timezone.now, required=False)

    class Meta:
        model = Post
        fields = (
            'title',
            'category',
            'content',
            'published_time',
            'slug',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'published_time' in self.fields:
            self.fields['published_time'].help_text = _("Leave blank to keep the post hidden.")

    def save(self, commit=True):
        post = super(PostCreationForm, self).save(commit=False)

        logger.debug("Setting post author to {}".format(self.user))
        if self.user is None:
            return None
        post.author = self.user

        # Generate slug
        post.slug = slugify_max(self.data['slug'], max_length=models.POST_SLUG_MAX_LENGTH)

        if commit:
            post.update_or_create(pk=post.pk)
        return post


class PostEditForm(forms.ModelForm):

    user = None
    published_time = flatpickr_datetime_field(required=False)

    class Meta:
        model = Post
        fields = (
            'title',
            'category',
            'content',
            'published_time',
            'slug',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'published_time' in self.fields:
            self.fields['published_time'].help_text = _("Leave blank to keep the post hidden.")

    def save(self, commit=True):
        post = super(PostEditForm, self).save(commit=False)
        if self.user is None:
            return None

        post.modified_time = timezone.now()

        if commit:
            post.update_or_create(pk=post.pk)
        return post
