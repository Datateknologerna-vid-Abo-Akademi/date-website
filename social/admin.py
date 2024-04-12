from django.contrib import admin

from .models import Harassment, IgUrl, HarassmentEmailRecipient


admin.site.register(IgUrl)
admin.site.register(Harassment)
admin.site.register(HarassmentEmailRecipient)
