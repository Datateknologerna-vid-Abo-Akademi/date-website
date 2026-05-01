from django.contrib import admin
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, StackedInline
from .models import Ctf, Flag, Guess


class FlagInline(StackedInline):
    model = Flag
    can_delete = True
    extra = 0
    exclude = ('solved_date',)
    autocomplete_fields = ('solver',)


@admin.register(Ctf)
class CtfAdmin(PublicUrlAdminMixin, ModelAdmin):
    model = Ctf
    save_on_top = True
    list_display = ('title', 'start_date', 'end_date', 'published')
    list_filter = ('published',)
    search_fields = ('title', 'slug')
    ordering = ('-start_date',)
    date_hierarchy = 'start_date'
    inlines = [
        FlagInline,
    ]


@admin.register(Flag)
class FlagAdmin(PublicUrlAdminMixin, ModelAdmin):
    list_display = ('title', 'ctf', 'solver', 'solved_date')
    list_filter = ('ctf',)
    search_fields = ('title', 'slug', 'flag', 'ctf__title', 'ctf__slug', 'solver__username', 'solver__email')
    autocomplete_fields = ('ctf', 'solver')
    list_select_related = ('ctf', 'solver')
    ordering = ('ctf', 'title')


@admin.register(Guess)
class GuessAdmin(ModelAdmin):
    list_display = ('ctf', 'flag', 'user', 'guess', 'timestamp', 'correct')
    list_filter = ('ctf', 'flag', 'correct')
    search_fields = ('ctf__title', 'ctf__slug', 'flag__title', 'flag__slug', 'user__username', 'user__email', 'guess')
    autocomplete_fields = ('ctf', 'flag', 'user')
    list_select_related = ('ctf', 'flag', 'user')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
