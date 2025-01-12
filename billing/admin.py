from django.contrib import admin

from .models import EventInvoice, EventBillingConfiguration

# Register your models here.

admin.site.register(EventInvoice)
admin.site.register(EventBillingConfiguration)
