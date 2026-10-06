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
    ordering = ('-created_time',)
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
