from django.contrib import admin
from .models import Ctf, Flag, Guess


# Register your models here.


class FlagInline(admin.TabularInline):
    model = Flag
    can_delete = True
    extra = 0
    exclude = ('solved_date',)


@admin.register(Ctf)
class CtfAdmin(admin.ModelAdmin):
    model = Ctf
    save_on_top = True
    inlines = [
        FlagInline,
    ]


@admin.register(Guess)
class GuessAdmin(admin.ModelAdmin):
    list_display = ('ctf', 'flag', 'user', 'guess', 'timestamp', 'correct')
    list_filter = ('ctf', 'flag', 'user', 'timestamp', 'correct')
    search_fields = ('ctf__title', 'flag__title', 'user__username', 'guess')
