from django.contrib import admin
from .models import StaticPage, StaticPageNav

# Register your models here.
admin.site.register(StaticPage)
admin.site.register(StaticPageNav)