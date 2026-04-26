from django.conf import settings
from django.contrib import admin
from core.admin_base import ModelAdmin, TabularInline

from core.admin import ActiveLanguageTranslationAdminMixin
from .models import Choice, Question, Vote

if settings.ENABLE_LANGUAGE_FEATURES:
    from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    class PollTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    # MRO when USE_UNFOLD=True: Mixin → TabbedTranslation → unfold.ModelAdmin → admin.ModelAdmin
    class PollTranslationAdminBase(ActiveLanguageTranslationAdminMixin, TabbedTranslationAdmin, ModelAdmin):
        pass
else:
    PollTranslationInlineBase = TabularInline
    PollTranslationAdminBase = ModelAdmin


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


class QuestionAdmin(PollTranslationAdminBase):
    fieldsets = [
        (None,
         {'fields':
             [
                 'question_text',
                 'voting_options',
                 'multiple_choice',
                 'required_multiple_choices',
                 'published',
                 'show_results',
                 'end_vote'
             ]}),
    ]
    list_display = ('question_text', 'pub_date', 'published', 'show_results', 'end_vote')
    inlines = [ChoiceInline, VoteInline]
    list_filter = ['published', 'show_results', 'end_vote', 'multiple_choice']
    search_fields = ['question_text', 'choice__choice_text', 'vote__user__username', 'vote__user__email']
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'


admin.site.register(Question, QuestionAdmin)
