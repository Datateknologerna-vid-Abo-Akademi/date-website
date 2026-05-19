from admin_ordering.admin import OrderableAdmin
from django.conf import settings
from django.contrib import admin
from django.db.models import Case, IntegerField, TextField, Value, When
from django_ckeditor_5.widgets import CKEditor5Widget

from core.admin import ActiveLanguageTranslationAdminMixin
from core.admin_base import UNFOLD_FORMFIELD_OVERRIDES, ModelAdmin, PublicUrlAdminMixin, TabularInline

from .models import StaticPage, StaticPageNav, StaticUrl

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


class UrlInline(OrderableAdmin, StaticPageTranslationInlineBase):
    model = StaticUrl
    fk_name = "category"
    can_delete = True
    extra = 0
    line_numbering = 0
    ordering_field = "dropdown_element"
    ordering = ["dropdown_element"]
    ordering_field_hide_input = True
    fields = ("dropdown_element", "title", "url", "parent", "logged_in_only")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                has_parent=Case(
                    When(parent__isnull=True, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("has_parent", "parent__dropdown_element", "dropdown_element")
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            queryset = StaticUrl.objects.filter(parent=None)
            object_id = request.resolver_match.kwargs.get("object_id") if request.resolver_match else None
            if object_id:
                queryset = queryset.filter(category_id=object_id)
            kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StaticPageNav)
class StaticPageNavAdmin(StaticPageTranslationAdminBase):
    model = StaticPageNav
    save_on_top = True
    list_display = ("category_name", "nav_element", "use_category_url", "url")
    search_fields = ("category_name", "url")
    ordering = ("nav_element",)
    inlines = [UrlInline]


@admin.register(StaticPage)
class StaticPageAdmin(PublicUrlAdminMixin, StaticPageTranslationAdminBase):
    model = StaticPage
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {"widget": CKEditor5Widget},
    }
    list_display = ("title", "slug", "members_only", "modified_time")
    search_fields = ("title", "slug")
    list_filter = ("members_only",)
    ordering = ("title",)
    date_hierarchy = "created_time"
