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
    list_display = ('user', 'flag', 'guess', 'timestamp')
    list_filter = ('user', 'flag', 'timestamp')
    search_fields = ('user__username', 'flag__title', 'guess')
