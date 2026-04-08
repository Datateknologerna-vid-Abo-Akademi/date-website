from django.apps import AppConfig
from django.contrib import admin
from django.contrib.admin import apps as admin_apps


class CoreConfig(AppConfig):
    name = 'date'
    default = True


class DateAdminConfig(admin_apps.AdminConfig):
    default_site = 'core.admin.FixedLanguageAdminSite'
    default = False

    def ready(self):
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
