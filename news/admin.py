from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from news import forms
from news.models import Post, Category


class CategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class PostAdmin(TabbedTranslationAdmin):

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
