import csv

from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse, re_path
from django.utils.html import format_html

from .models import EventInvoice, EventBillingConfiguration
from .util import BillingIntegrations

# Register your models here.

admin.site.register(EventInvoice)


@admin.register(EventBillingConfiguration)
class EventBillingConfigurationAdmin(admin.ModelAdmin):
    list_display = ('event', 'due_date', 'integration_type', 'price', 'price_selector', 'ref_export')
    list_filter = ('integration_type',)
    search_fields = ('event__title',)
    ordering = ('event',)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            re_path(r'^(?P<conf_id>.+)/ref_numbers/$', self.ref_numbers, name='billing_ref_numbers'),
        ]
        return my_urls + urls

    def ref_export(self, obj):
        return format_html(
            '<a class="button" href={}>Exportera data</a>&nbsp;',
            reverse('admin:billing_ref_numbers', args=[obj.pk])
        )

    ref_export.short_description = 'Exportera data'
    ref_export.allow_tags = True

    def ref_numbers(self, request, conf_id):
        bconfig = self.get_object(request, conf_id)
        event = bconfig.event

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{event.title}_ref_numbers.csv"'}
        )

        if bconfig.integration_type == BillingIntegrations.INVOICE.value:
            invoices = EventInvoice.objects.filter(participant__event=event)
            fieldnames = ['name', 'email', 'invoice_number', 'reference_number', 'invoice_date', 'due_date', 'amount',
                          'currency']
            writer = csv.DictWriter(response, fieldnames=fieldnames)
            writer.writeheader()
            for invoice in invoices:
                writer.writerow({
                    'name': invoice.participant.user,
                    'email': invoice.participant.email,
                    'invoice_number': invoice.invoice_number,
                    'reference_number': invoice.reference_number,
                    'invoice_date': invoice.invoice_date,
                    'due_date': invoice.due_date,
                    'amount': invoice.amount,
                    'currency': invoice.currency
                })
        else:
            return HttpResponse("Integration not supported", 400)

        return response
