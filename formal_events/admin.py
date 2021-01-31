from django.contrib import admin

from .models import Formal_Event, Formal_Static_Page

# Register your models here.

#TODO REGISTER NEEDED ADMIN MODELS



class Formal_Static_Page_Inline(admin.TabularInline):
    model = Formal_Static_Page
    extra = 0

@admin.register(Formal_Event)
class Formal_Events_Admin(admin.ModelAdmin):
    inlines = [
        Formal_Static_Page_Inline
    ]
