from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django_ckeditor_5.widgets import CKEditor5Widget
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, UNFOLD_FORMFIELD_OVERRIDES

from core.admin import ActiveLanguageTranslationAdminMixin
from news import forms
from news.models import Post, Category

if settings.ENABLE_LANGUAGE_FEATURES:
    from modeltranslation.admin import TabbedTranslationAdmin

    class NewsTranslationAdminBase(ActiveLanguageTranslationAdminMixin, TabbedTranslationAdmin, ModelAdmin):
        pass
else:
    NewsTranslationAdminBase = ModelAdmin


class CategoryAdmin(PublicUrlAdminMixin, NewsTranslationAdminBase):
    list_display = ('name',)
    search_fields = ('name', 'slug')
    ordering = ('name',)


class PostAdmin(PublicUrlAdminMixin, NewsTranslationAdminBase):
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }

    fieldsets = [
        (None, {'fields': ['title', 'category', 'content', 'published', 'slug']}),
    ]
    list_display = ('title', 'author', 'category', 'created_time', 'modified_time', 'published')
    search_fields = ('title', 'slug', 'category__name', 'category__slug', 'author__username', 'author__first_name', 'author__last_name', 'author__email')
    list_filter = ('published', 'category')
    autocomplete_fields = ('author', 'category')
    list_select_related = ('author', 'category')
    ordering = ('-created_time',)
    date_hierarchy = 'created_time'

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs['form'] = forms.PostCreationForm
        else:
            kwargs['form'] = forms.PostEditForm

        form = super().get_form(request, obj, change=change, **kwargs)
        form.user = request.user
        return form


admin.site.register(Category, CategoryAdmin)
admin.site.register(Post, PostAdmin)
