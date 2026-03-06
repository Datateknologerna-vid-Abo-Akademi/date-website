from django.contrib import admin


class FixedLanguageAdminSite(admin.AdminSite):
    """Mirror the default admin site while preserving normal locale resolution."""


admin_site = FixedLanguageAdminSite()

for model, model_admin in admin.site._registry.items():
    admin_site._registry[model] = model_admin.__class__(model, admin_site)
