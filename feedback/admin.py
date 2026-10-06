from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin import ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin
from core.admin_base import ModelAdmin

from .models import FeedbackEmailRecipient, FeedbackFormSettings, FeedbackSubmission


@admin.register(FeedbackSubmission)
class FeedbackSubmissionAdmin(ModelAdmin):
    list_display = ('email', 'message_preview', 'created_time')
    search_fields = ('email', 'message')
    # No explicit ordering: it would only repeat FeedbackSubmission.Meta.ordering.
    # created_time defaults to timezone.now() on save; without this, the add
    # form requires typing a timestamp by hand instead of auto-filling one.
    readonly_fields = ('created_time',)

    @admin.display(description=_('Meddelande'))
    def message_preview(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message


@admin.register(FeedbackEmailRecipient)
class FeedbackEmailRecipientAdmin(ModelAdmin):
    list_display = ('recipient_email',)
    search_fields = ('recipient_email',)
    ordering = ('recipient_email',)


if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]

    class FeedbackFormSettingsTranslationAdminBase(
        ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin
    ):
        pass
else:
    FeedbackFormSettingsTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


@admin.register(FeedbackFormSettings)
class FeedbackFormSettingsAdmin(FeedbackFormSettingsTranslationAdminBase):
    list_display = ('__str__', 'intro_text')

    def get_fields(self, request, obj=None):
        # With the multilingual UI off the site runs Swedish only and the public
        # page reads intro_text_sv. The base intro_text column is not what the
        # site reads: modeltranslation resolves the field to the active language
        # column (sv) and syncs the base column from it, so an edit typed into
        # the plain intro_text field is silently discarded. Show the column the
        # site reads instead. Decided at request time rather than by the admin
        # base class chosen at import time, so a test can flip the setting with
        # override_settings.
        if not settings.ENABLE_LANGUAGE_FEATURES:
            return ['intro_text_sv']
        return super().get_fields(request, obj)

    def get_fieldsets(self, request, obj=None):
        # Same reason as get_fields: with the multilingual UI off the change
        # form must edit exactly the one column the site reads. Stated here as
        # well so the guarantee holds whichever admin base class was picked at
        # import time (the tabbed base class derives its fieldsets from the
        # form, not from get_fields).
        if not settings.ENABLE_LANGUAGE_FEATURES:
            return [(None, {'fields': ['intro_text_sv']})]
        return super().get_fieldsets(request, obj)

    def get_queryset(self, request):
        # Pin the changelist to the row the site reads (the lowest pk), so a row
        # created out of band at another pk can never be edited while having no
        # effect on /forms/. Computed with a plain query rather than get_solo()
        # so a GET of the changelist does not create the row.
        solo_pk = FeedbackFormSettings.objects.order_by('pk').values_list('pk', flat=True).first()
        queryset = super().get_queryset(request)
        if solo_pk is None:
            return queryset
        return queryset.filter(pk=solo_pk)

    def has_add_permission(self, request):
        return not FeedbackFormSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
