from django.contrib import admin

from .models import Choice, Question, RightToVote, User, Vote


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    readonly_fields = ['votes']

class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ['user']

    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def full_name(self, obj):
        return obj.user.get_full_name()

class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None,               {'fields': ['question_text', 'multiple_choice', 'members_only', 'ordinary_members_only', 'vote_members_only', 'published', 'show_results', 'end_vote', 'right_to_vote']}),
    ]
    list_display = ('question_text', 'pub_date',)
    inlines = [ChoiceInline, VoteInline]
    list_filter = ['pub_date']
    search_fields = ['question_text']

admin.site.register(Question, QuestionAdmin)

class UserInline(admin.TabularInline):
    model = User
    extra = 0
    def full_name(self, obj):
        return obj.user.get_full_name()

@admin.register(RightToVote)
class RightToVoteAdmin(admin.ModelAdmin):
    Model = RightToVote
    list_display = ('reason',)
    inlines = [UserInline]

