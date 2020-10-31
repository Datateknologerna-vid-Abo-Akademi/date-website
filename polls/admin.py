from django.contrib import admin

from .models import Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    readonly_fields = ['votes']


class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None,               {'fields': ['question_text', 'multiple_choice', 'members_only', 'ordinary_members_only', 'published', 'show_results']}),
    ]
    list_display = ('question_text', 'pub_date')
    inlines = [ChoiceInline]
    list_filter = ['pub_date']
    search_fields = ['question_text']

admin.site.register(Question, QuestionAdmin)