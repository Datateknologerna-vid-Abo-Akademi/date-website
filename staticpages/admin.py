from django.contrib import admin

from .models import StaticPage, StaticPageNav, StaticUrl

# Register your models here.

class PageInline(admin.TabularInline):
    model = StaticPage
    can_delete = True
    extra = 0

class UrlInline(admin.TabularInline):
    model = StaticUrl
    can_delete = True
    extra = 0

@admin.register(StaticPageNav)
class StaticPageNavAdmin(admin.ModelAdmin):
    model = StaticPageNav
    save_on_top = True
    inlines = [
        PageInline,
        UrlInline,
    ]

admin.site.register(StaticPage)