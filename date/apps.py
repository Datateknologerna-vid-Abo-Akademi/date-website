from django.apps import AppConfig
from django.contrib import admin
from django.contrib.admin import apps as admin_apps


class CoreConfig(AppConfig):
    name = 'date'
    default = True

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from ads.models import AdUrl
        from date.views import bump_homepage_version
        from events.models import Event
        from instagram.models import IgUrl
        from news.models import Post

        # The cached anonymous homepage context (date/views.py) depends on
        # these models; bump the version so admin edits show up immediately
        # instead of waiting out the TTL backstop.
        for model in (Event, Post, AdUrl, IgUrl):
            label = model._meta.label_lower
            post_save.connect(
                bump_homepage_version,
                sender=model,
                dispatch_uid=f"homepage-invalidate-{label}",
            )
            post_delete.connect(
                bump_homepage_version,
                sender=model,
                dispatch_uid=f"homepage-invalidate-del-{label}",
            )


class DateAdminConfig(admin_apps.AdminConfig):
    default_site = 'core.admin.FixedLanguageAdminSite'
    default = False

    def ready(self):
        # Importing core.admin here installs FixedLanguageAdminSite as admin.site
        # (overriding any Unfold-supplied default) before autodiscovery registers
        # models on it. The admin_site reference is captured at the same time.
        from core import admin as core_admin  # noqa: F401

        super().ready()

        from django_otp.plugins.otp_static.models import StaticDevice
        from django_otp.plugins.otp_totp.models import TOTPDevice

        # Remove standalone OTP device admins after autodiscovery has registered
        # them on the default site. Devices are managed through the Member inline.
        for model in (TOTPDevice, StaticDevice):
            try:
                admin.site.unregister(model)
            except admin.sites.NotRegistered:
                pass
