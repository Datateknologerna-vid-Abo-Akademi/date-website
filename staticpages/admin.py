from django.contrib import admin

from .models import StaticPage, StaticPageNav, StaticUrl

# Register your models here.
admin.site.register(StaticPage)
admin.site.register(StaticPageNav)
admin.site.register(StaticUrl)