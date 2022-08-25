from django.contrib import admin
from ctf.models import Ctf, Flag

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