from django.apps import AppConfig


class MemberConfig(AppConfig):
    name = 'members'

    def ready(self):
        from .key_management import ensure_signing_key, patch_dot_settings
        ensure_signing_key()
        patch_dot_settings()
