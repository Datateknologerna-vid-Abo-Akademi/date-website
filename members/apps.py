from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MemberConfig(AppConfig):
    name = 'members'

    def ready(self):
        from .provisioning import provision_membership_access

        # Run after each app's permissions are created. The final call sees the
        # complete permission set, while update_or_create/set keep this safe.
        post_migrate.connect(provision_membership_access, dispatch_uid='members.provision_membership_access')
