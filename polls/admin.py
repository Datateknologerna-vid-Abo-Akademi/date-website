from django.conf import settings
from django.contrib import admin
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from core.admin import (
    ActiveLanguageTranslationAdminMixin,
    LanguageTabbedTranslationAdmin,
    TranslationCompletionAdminMixin,
)
from core.admin_base import ModelAdmin, TabularInline
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    FlatpickrDateTimeAdminMixin,
)

from .models import Choice, Question, Vote

if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]
    from modeltranslation.admin import TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    class PollTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    class PollTranslationAdminBase(ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin):
        pass
else:
    PollTranslationInlineBase = TabularInline  # type: ignore[misc, assignment]
    PollTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


class ChoiceInline(PollTranslationInlineBase):
    model = Choice
    extra = 0
    readonly_fields = ['votes']


class VoteInline(TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ['user']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def full_name(self, obj):
        return obj.user.get_full_name()


class QuestionPublicationFilter(admin.SimpleListFilter):
    title = _('publicering')
    parameter_name = 'publication'

    def lookups(self, request, model_admin):
        return (
            ('published', _('Publicerad')),
            ('scheduled', _('Schemalagd')),
            ('hidden', _('Dold')),
        )

    def queryset(self, request, queryset):
        current_time = now()
        if self.value() == 'published':
            return queryset.filter(published_time__isnull=False, published_time__lte=current_time)
        if self.value() == 'scheduled':
            return queryset.filter(published_time__gt=current_time)
        if self.value() == 'hidden':
            return queryset.filter(published_time__isnull=True)
        return queryset


class QuestionAdmin(FlatpickrDateTimeAdminMixin, TranslationCompletionAdminMixin, PollTranslationAdminBase):
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'question_text',
                    'voting_options',
                    'multiple_choice',
                    'required_multiple_choices',
                    'published_time',
                    'show_results',
                    'end_vote',
                ]
            },
        ),
    ]
    list_display = (
        'question_text',
        'translation_status',
        'pub_date',
        'publication_status',
        'published_time',
        'show_results',
        'end_vote',
    )
    inlines = [ChoiceInline, VoteInline]
    list_filter = [QuestionPublicationFilter, 'show_results', 'end_vote', 'multiple_choice']
    search_fields = ['question_text', 'choice__choice_text', 'vote__user__username', 'vote__user__email']
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'

    @admin.display(description=_("Publicering"), ordering="published_time")
    def publication_status(self, obj):
        if obj.published_time is None:
            return _('Dold')
        if obj.published_time > now():
            return _('Schemalagd')
        return _('Publicerad')

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS


admin.site.register(Question, QuestionAdmin)
