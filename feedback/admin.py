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

    def has_add_permission(self, request):
        return not FeedbackFormSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
