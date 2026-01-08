from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.cache_keys import DATE_INDEX_CACHE_KEY, EVENTS_INDEX_CACHE_KEY
from .models import Event


def clear_event_page_cache():
    for key in (DATE_INDEX_CACHE_KEY, EVENTS_INDEX_CACHE_KEY):
        cache.delete(key)


@receiver(post_save, sender=Event)
def event_saved(sender, **kwargs):
    clear_event_page_cache()


@receiver(post_delete, sender=Event)
def event_deleted(sender, **kwargs):
    clear_event_page_cache()
