from django.apps import AppConfig
from django.contrib.admin import apps as admin_apps


class CoreConfig(AppConfig):
    name = 'date'
    default = True


class DateAdminConfig(admin_apps.AdminConfig):
    default_site = 'core.admin.FixedLanguageAdminSite'
    default = False
