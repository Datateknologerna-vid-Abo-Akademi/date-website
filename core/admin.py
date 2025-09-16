from django.contrib import admin
from django.utils import translation


class FixedLanguageAdminSite(admin.AdminSite):
    def each_context(self, request):
        # Force swedish as admin panel language
        translation.activate('sv')
        request.LANGUAGE_CODE = 'sv'
        return super().each_context(request)


admin_site = FixedLanguageAdminSite()

for model, model_admin in admin.site._registry.items():
    admin_site._registry[model] = model_admin.__class__(model, admin_site)
