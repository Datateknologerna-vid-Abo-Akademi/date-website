from contextvars import ContextVar

from django.conf import settings
from django.contrib import admin
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.admin import AdminSiteOTPRequiredMixin


_active_translation_request = ContextVar("active_translation_request", default=None)


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

    def _replace_fieldsets_with_active_languages(self, fieldsets):
        fieldsets_new = []
        for name, options in fieldsets:
            options = {**options}
            if "fields" in options:
                options["fields"] = self.replace_orig_field(options["fields"])
            fieldsets_new.append((name, options))
        return fieldsets_new

    def replace_orig_field(self, option):
        fields = super().replace_orig_field(option)
        request = _active_translation_request.get()
        if request is None:
            return fields
        return self._filter_admin_translation_fields(fields, request)

    def _get_form_or_formset(self, request, obj=None, **kwargs):
        token = _active_translation_request.set(request)
        try:
            kwargs = super()._get_form_or_formset(request, obj, **kwargs)

            hidden_fields = self._hidden_admin_translation_fields(request)
            if hidden_fields:
                exclude = kwargs.get("exclude")
                exclude = [] if exclude is None else list(exclude)
                exclude.extend(field for field in hidden_fields if field not in exclude)
                kwargs["exclude"] = tuple(exclude)

            return kwargs
        finally:
            _active_translation_request.reset(token)

    def _get_declared_fieldsets(self, request, obj=None):
        token = _active_translation_request.set(request)
        try:
            if not self.fields and hasattr(self.form, "_meta") and self.form._meta.fields:
                self.fields = self.form._meta.fields

            fieldsets = (
                self.add_fieldsets
                if getattr(self, "add_fieldsets", None) and obj is None
                else self.fieldsets
            )
            if fieldsets:
                return self._replace_fieldsets_with_active_languages(fieldsets)
            if self.fields:
                return [(None, {"fields": self.replace_orig_field(self.get_fields(request, obj))})]
            return None
        finally:
            _active_translation_request.reset(token)

    def _get_fieldsets_post_form_or_formset(self, request, form, obj=None):
        token = _active_translation_request.set(request)
        try:
            return super()._get_fieldsets_post_form_or_formset(request, form, obj)
        finally:
            _active_translation_request.reset(token)


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
