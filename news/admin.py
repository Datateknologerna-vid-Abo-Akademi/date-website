from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django_ckeditor_5.widgets import CKEditor5Widget
from modeltranslation.admin import TabbedTranslationAdmin

from news import forms
from news.models import Post, Category

NewsTranslationAdminBase = TabbedTranslationAdmin if settings.ENABLE_LANGUAGE_FEATURES else admin.ModelAdmin


class CategoryAdmin(NewsTranslationAdminBase):
    list_display = ('name',)
    search_fields = ('name',)


class PostAdmin(NewsTranslationAdminBase):
    formfield_overrides = {
        TextField: {'widget': CKEditor5Widget},
    }

    fieldsets = [
        (None, {'fields': ['title', 'category', 'content', 'published', 'slug']}),
    ]
    list_display = ('title', 'author', 'category', 'created_time', 'modified_time', 'published')
    search_fields = ('title', 'author', 'created_time')

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
