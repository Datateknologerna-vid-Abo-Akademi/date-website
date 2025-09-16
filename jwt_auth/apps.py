from django.apps import AppConfig


class JwtAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jwt_auth'
    verbose_name = 'JWT Authentication'

    def ready(self):
        """
        Import signal handlers when the app is ready.
        """
        import jwt_auth.signals  # noqa
