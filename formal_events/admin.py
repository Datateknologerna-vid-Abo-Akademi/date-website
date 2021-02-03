from django.contrib import admin

from .models import FormalEvent, FormalStaticPage

# Register your models here.

#TODO REGISTER NEEDED ADMIN MODELS



class FormalStaticPageInline(admin.TabularInline):
    model = FormalStaticPage
    extra = 0

@admin.register(FormalEvent)
class FormalEventsAdmin(admin.ModelAdmin):
    inlines = [
        FormalStaticPageInline
    ]
