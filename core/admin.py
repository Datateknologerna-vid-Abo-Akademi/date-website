from django.conf import settings
from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice
from modeltranslation.admin import TranslationAdmin
from two_factor.admin import AdminSiteOTPRequiredMixin

if getattr(settings, 'USE_UNFOLD', False):
    from unfold.sites import UnfoldAdminSite

    _AdminSiteBase = UnfoldAdminSite  # type: ignore[misc, assignment]
else:
    _AdminSiteBase = admin.AdminSite  # type: ignore[misc, assignment]


def get_admin_translation_languages() -> tuple[str, ...]:
    """Return language codes that should be shown in modeltranslation admin UI."""
    configured_languages = getattr(settings, "LANGUAGES", ())
    return tuple(code for code, _label in configured_languages)


class LanguageTabbedTranslationAdmin(TranslationAdmin):
    """Translation admin with local, form-wide language tabs.

    django-modeltranslation's bundled tabbed admin depends on jQuery UI from a
    CDN. Keep the editor usable without that external dependency.
    """

    class Media:
        css = {"all": ("common/css/admin_translation_tabs.css",)}
        js = ("common/js/admin_translation_tabs.js",)


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
            for translation_fields in self.trans_opts.all_fields.values()  # type: ignore[attr-defined]
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


class TranslationCompletionAdminMixin:
    """Show how many translated fields are complete for each active language."""

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if settings.ENABLE_LANGUAGE_FEATURES:
            return list_display
        return tuple(field for field in list_display if field != "translation_status")

    @admin.display(description=_("Language"))
    def translation_status(self, obj):
        trans_opts = getattr(self, "trans_opts", None)
        if trans_opts is None:
            return "-"
        translated_fields = tuple(trans_opts.all_fields)
        if not translated_fields:
            return "-"

        statuses = []
        for language in self.get_admin_translation_languages(None):
            completed = sum(
                bool(str(getattr(obj, f"{field_name}_{language}", "") or "").strip())
                for field_name in translated_fields
            )
            statuses.append(f"{language}: {completed}/{len(translated_fields)}")
        return "; ".join(statuses)


class ReferringObjectAutocompleteJsonView(AutocompleteJsonView):
    """Also allow autocomplete for editors of the object that owns the field.

    Django's ``AutocompleteJsonView`` only answers when the user holds view
    permission on the *related* model. Several models here point at
    ``members.Member`` through ``autocomplete_fields`` (``Flag.solver``,
    ``Event.author``, ``Functionary.member``, ``EventInvoice.participant`` ...),
    and the editors who maintain those objects are deliberately not trusted with
    the full member registry. Without this, their member dropdowns come back
    empty ("no results").

    Being allowed to add or change the referring object is treated as enough to
    search the related model for choices. The related ``ModelAdmin`` still owns
    ``get_queryset``/``get_search_results``, so per-group row restrictions such
    as ``MEMBER_ADMIN_RESTRICTED_GROUP`` keep applying to the returned rows.
    """

    def has_perm(self, request, obj=None):
        if super().has_perm(request, obj=obj):
            return True
        return self._referring_admin_grants_access(request)

    def _referring_admin_grants_access(self, request):
        source_model = self.source_field.model
        field_name = self.source_field.name
        for model_admin in self.admin_site._registry.values():
            for candidate in self._referring_candidates(model_admin, source_model):
                if field_name not in candidate.get_autocomplete_fields(request):
                    continue
                if self._can_write(request, candidate):
                    return True
        return False

    @staticmethod
    def _referring_candidates(model_admin, source_model):
        if model_admin.model is source_model:
            yield model_admin
        for inline_class in model_admin.inlines:
            if inline_class.model is source_model:
                yield inline_class(model_admin.model, model_admin.admin_site)

    @staticmethod
    def _can_write(request, candidate):
        if candidate.has_change_permission(request):
            return True
        if isinstance(candidate, InlineModelAdmin):
            return candidate.has_add_permission(request, None)
        return candidate.has_add_permission(request)


class FixedLanguageAdminSite(AdminSiteOTPRequiredMixin, _AdminSiteBase):  # type: ignore[misc, valid-type]
    """Mirror the default admin site while preserving normal locale resolution."""

    def autocomplete_view(self, request):
        return ReferringObjectAutocompleteJsonView.as_view(admin_site=self)(request)

    def has_permission(self, request):
        if not admin.AdminSite.has_permission(self, request):
            return False

        # Allow access when the user has no 2FA device registered (2FA is optional).
        # When a device exists the user must have completed OTP verification this session.
        has_totp = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
        return request.user.is_verified() or not has_totp


# When USE_UNFOLD=True, unfold's DefaultAppConfig.ready() preempts Django's lazy
# DefaultAdminSite by directly assigning a plain UnfoldAdminSite to admin.site,
# which bypasses our 2FA-enforcing FixedLanguageAdminSite. Reinstall our subclass
# here (this module is imported from DateAdminConfig.ready() before autodiscovery)
# so model registrations and URL routing land on the OTP-aware site.
if not isinstance(admin.site, FixedLanguageAdminSite):
    _site = FixedLanguageAdminSite()
    admin.site = _site
    from django.contrib.admin import sites as _admin_sites

    _admin_sites.site = _site

admin_site = admin.site
