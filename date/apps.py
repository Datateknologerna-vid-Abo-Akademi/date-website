from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class CoreConfig(AppConfig):
    name = 'date'


class DateAdminConfig(AdminConfig):
    default_site = 'core.admin.FixedLanguageAdminSite'
