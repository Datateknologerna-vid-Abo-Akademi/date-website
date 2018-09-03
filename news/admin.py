from news import forms
from django.contrib import admin

from news.models import Post


#class PostAdmin(admin.ModelAdmin):
#   form = forms.PostCreationForm


admin.site.register(Post)
