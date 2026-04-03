from django.apps import AppConfig


class MemberConfig(AppConfig):
    name = 'members'

    def ready(self):
        import members.signals  # noqa: F401
