from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class StaticpagesConfig(AppConfig):
    name = 'staticpages'

    def ready(self):
        from . import context_processors
        from .models import StaticPageNav, StaticUrl

        # Admin edits to the navigation must be visible immediately: bump the
        # cache version on every change.
        for model in (StaticUrl, StaticPageNav):
            post_save.connect(
                context_processors.invalidate_nav_cache,
                sender=model,
                dispatch_uid=f"nav-save-{model.__name__}",
            )
            post_delete.connect(
                context_processors.invalidate_nav_cache,
                sender=model,
                dispatch_uid=f"nav-delete-{model.__name__}",
            )
