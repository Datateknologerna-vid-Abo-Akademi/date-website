from django.shortcuts import render
from django.contrib.syndication.views import Feed
from django.urls import reverse

from . import models

class LatestPosts(Feed):
    title = "DaTe nyheter"
    link = "/news/feed"
    description = "DaTe nyhetsflöde"

    def items(self):
        return models.Post.objects.order_by('modified_time')[:5]

    def get_description(self, item):
        return item.content[:50] + "..."

    def get_author(self, item):
        return item.author

    def get_created_time(self, item):
        return item.created_time

    def get_modified_time(self, item):
        return item.modified_time

    def item_link(self, item):
        return reverse('article-detail', args=[item.slug])
