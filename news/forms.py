import logging
from django import forms
from django.utils import timezone

from date.functions import slugify_max
from news import models
from news.models import Post

logger = logging.getLogger('date')


class PostCreationForm(forms.ModelForm):

    user = None

    class Meta:
        model = Post
        fields = (
            'title',
            'content',
            'published',
            'slug'
        )

    def save(self, commit=True):
        post = super(PostCreationForm, self).save(commit=False)

        logger.debug("Setting post author to {}".format(self.user))
        if self.user is None:
            return None
        post.author = self.user

        # Generate slug
        post.slug = slugify_max(self.data['slug'], max_length=models.POST_SLUG_MAX_LENGTH)

        if post.published:
            post.published_time = timezone.now()

        if commit:
            post.update_or_create(pk=post.pk)
        return post


class PostEditForm(forms.ModelForm):

    user = None

    class Meta:
        model = Post
        fields = (
            'title',
            'content',
            'published',
            'slug'
        )

    def save(self, commit=True):
        post = super(PostEditForm, self).save(commit=False)
        if self.user is None:
            return None

        post.modified_time = timezone.now()

        if commit:
            post.update_or_create(pk=post.pk)
        return post
