from admin_ordering.admin import OrderableAdmin
from django.contrib import admin

from .models import StaticPage, StaticPageNav, StaticUrl


# Register your models here.


class UrlInline(OrderableAdmin, admin.TabularInline):
    model = StaticUrl
    can_delete = True
    extra = 0


@admin.register(StaticPageNav)
class StaticPageNavAdmin(admin.ModelAdmin):
    model = StaticPageNav
    save_on_top = True
    inlines = [
        UrlInline,
    ]


admin.site.register(StaticPage)
