from news import forms
from django.contrib import admin

from news.models import Post


class PostAdmin(admin.ModelAdmin):

    def add_view(self, request, form_url='', extra_context=None):
        self.fields = forms.PostCreationForm.Meta.fields
        return super(PostAdmin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.fields = forms.PostEditForm.Meta.fields
        return super(PostAdmin, self).change_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            form = forms.PostCreationForm
        else:
            form = forms.PostEditForm

        form.user = request.user
        return form


admin.site.register(Post, PostAdmin)
