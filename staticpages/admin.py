from admin_ordering.admin import OrderableAdmin
from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django_ckeditor_5.widgets import CKEditor5Widget
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, TabularInline, UNFOLD_FORMFIELD_OVERRIDES

from .models import StaticPage, StaticPageNav, StaticUrl
from core.admin import ActiveLanguageTranslationAdminMixin

if settings.ENABLE_LANGUAGE_FEATURES:
    from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    class StaticPageTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    # MRO when USE_UNFOLD=True: Mixin → TabbedTranslation → unfold.ModelAdmin → admin.ModelAdmin
    class StaticPageTranslationAdminBase(ActiveLanguageTranslationAdminMixin, TabbedTranslationAdmin, ModelAdmin):
        pass
else:
    StaticPageTranslationInlineBase = TabularInline
    StaticPageTranslationAdminBase = ModelAdmin


# Register your models here.


class UrlInline(OrderableAdmin, StaticPageTranslationInlineBase):
    model = StaticUrl
    can_delete = True
    extra = 0
    line_numbering = 0
    ordering_field = 'dropdown_element'
    ordering = ['dropdown_element']
    ordering_field_hide_input = True
    fields = ('dropdown_element', 'title', 'url', 'logged_in_only')


@admin.register(StaticPageNav)
class StaticPageNavAdmin(StaticPageTranslationAdminBase):
    model = StaticPageNav
    save_on_top = True
    list_display = ('category_name', 'nav_element', 'use_category_url', 'url')
    search_fields = ('category_name', 'url')
    ordering = ('nav_element',)
    inlines = [UrlInline]


@admin.register(StaticPage)
class StaticPageAdmin(PublicUrlAdminMixin, StaticPageTranslationAdminBase):
    model = StaticPage
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }
    list_display = ('title', 'slug', 'members_only', 'modified_time')
    search_fields = ('title', 'slug')
    list_filter = ('members_only',)
    ordering = ('title',)
    date_hierarchy = 'created_time'
    prepopulated_fields = {'slug': ('title',)}
