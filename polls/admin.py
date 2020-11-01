from django.contrib import admin

from .models import Choice, Question, Suffrage


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    readonly_fields = ['votes']


class SuffrageInline(admin.TabularInline):
    model = Suffrage
    extra = 0
    llist_display = ('user_full_name',)
    def user_full_name(self, obj):
        return obj.user.get_full_name()


class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None,               {'fields': ['question_text', 'multiple_choice', 'members_only', 'ordinary_members_only', 'vote_members_only', 'published', 'show_results']}),
    ]
    list_display = ('question_text', 'pub_date')
    inlines = [ChoiceInline, SuffrageInline]
    list_filter = ['pub_date']
    search_fields = ['question_text']

admin.site.register(Question, QuestionAdmin)