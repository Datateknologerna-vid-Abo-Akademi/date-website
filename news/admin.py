from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from news import forms
from news.models import Post, Category


class CategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class PostAdmin(TabbedTranslationAdmin):

    list_display = ('title', 'author', 'category', 'created_time', 'modified_time', 'published')
    search_fields = ('title', 'author', 'created_time')

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            form = forms.PostCreationForm
        else:
            form = forms.PostEditForm

        form.user = request.user
        return form


admin.site.register(Category, CategoryAdmin)
admin.site.register(Post, PostAdmin)
