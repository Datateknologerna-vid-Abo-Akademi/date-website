from django.conf import settings
from django.contrib import admin
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.admin import AdminSiteOTPRequiredMixin


def get_admin_translation_languages() -> tuple[str, ...]:
    """Return language codes that should be shown in modeltranslation admin UI."""
    configured_languages = getattr(settings, "LANGUAGES", ())
    return tuple(code for code, _label in configured_languages)


class ActiveLanguageTranslationAdminMixin:
    """Hide translated admin fields that are outside the active language set."""

    def get_admin_translation_languages(self, request):
        return get_admin_translation_languages()

    def _hidden_admin_translation_fields(self, request) -> set[str]:
        visible_languages = set(self.get_admin_translation_languages(request))
        if not visible_languages:
            return set()

        return {
            field.name
            for translation_fields in self.trans_opts.all_fields.values()
            for field in translation_fields
            if field.language not in visible_languages
        }

    def _filter_admin_translation_fields(self, fields, request):
        hidden_fields = self._hidden_admin_translation_fields(request)
        if not hidden_fields:
            return fields

        filtered_fields = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                filtered_fields.append(self._filter_admin_translation_fields(field, request))
            elif field not in hidden_fields:
                filtered_fields.append(field)
        return tuple(filtered_fields) if isinstance(fields, tuple) else filtered_fields

    def get_exclude(self, request, obj=None):
        exclude = super().get_exclude(request, obj)
        exclude = () if exclude is None else tuple(exclude)
        hidden_fields = self._hidden_admin_translation_fields(request)
        return exclude + tuple(field for field in hidden_fields if field not in exclude)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        filtered_fieldsets = []
        for name, options in fieldsets:
            options = {**options}
            if "fields" in options:
                options["fields"] = self._filter_admin_translation_fields(options["fields"], request)
            filtered_fieldsets.append((name, options))
        return filtered_fieldsets


class FixedLanguageAdminSite(AdminSiteOTPRequiredMixin, admin.AdminSite):
    """Mirror the default admin site while preserving normal locale resolution."""

    def has_permission(self, request):
        if not admin.AdminSite.has_permission(self, request):
            return False

        # Allow access when the user has no 2FA device registered (2FA is optional).
        # When a device exists the user must have completed OTP verification this session.
        has_totp = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
        return request.user.is_verified() or not has_totp


admin_site = admin.site
