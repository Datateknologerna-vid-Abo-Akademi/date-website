from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MemberConfig(AppConfig):
    name = 'members'

    def ready(self):
        from django.core.checks import Tags, register

        from . import webauthn  # noqa: F401  (connects the recent-auth login signal)
        from .checks import check_passkey_settings
        from .provisioning import provision_membership_access

        register(check_passkey_settings, Tags.security)

        # Run after each app's permissions are created. The final call sees the
        # complete permission set, while update_or_create/set keep this safe.
        post_migrate.connect(provision_membership_access, dispatch_uid='members.provision_membership_access')
