from admin_ordering.admin import OrderableAdmin
from django.contrib import admin

from .models import StaticPage, StaticPageNav, StaticUrl


# Register your models here.


class UrlInline(OrderableAdmin, admin.TabularInline):
    model = StaticUrl
    can_delete = True
    extra = 0
    line_numbering = 0
    ordering_field = ('dropdown_element',)
    ordering = ['dropdown_element']
    ordering_field_hide_input = True
    fields = ('dropdown_element', 'title', 'url', 'logged_in_only')


@admin.register(StaticPageNav)
class StaticPageNavAdmin(admin.ModelAdmin):
    model = StaticPageNav
    save_on_top = True
    inlines = [
        UrlInline,
    ]


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    model = StaticPage
    list_display = ('title', 'slug', 'members_only')
