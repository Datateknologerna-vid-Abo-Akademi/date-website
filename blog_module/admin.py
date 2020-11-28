from django.contrib import admin
from .models import Blog, Comment


# Register your models here.
admin.site.register(Blog)
admin.site.register(Comment)