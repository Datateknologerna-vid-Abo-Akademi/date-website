from django.contrib import admin


class FixedLanguageAdminSite(admin.AdminSite):
    """Mirror the default admin site while preserving normal locale resolution."""


admin_site = admin.site
