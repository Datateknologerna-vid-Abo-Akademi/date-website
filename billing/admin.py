import csv

from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from core.admin_base import ExtraChangeListLinksMixin, ModelAdmin
from core.admin_ui import AdminLink

from .models import EventBillingConfiguration, EventInvoice
from .util import BillingIntegrations


@admin.register(EventInvoice)
class EventInvoiceAdmin(ModelAdmin):
    list_display = (
        'participant',
        'event_link',
        'invoice_number',
        'reference_number',
        'invoice_date',
        'due_date',
        'amount',
        'currency',
    )
    search_fields = (
        'invoice_number',
        'reference_number',
        'participant__user',
        'participant__email',
        'participant__event__title',
        'participant__event__slug',
    )
    list_filter = ('participant__event', 'currency')
    autocomplete_fields = ('participant',)
    list_select_related = ('participant', 'participant__event')
    ordering = ('-invoice_date',)
    date_hierarchy = 'invoice_date'

    @admin.display(description=_('Event'))
    def event_link(self, obj):
        event = obj.participant.event
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:events_event_change', args=[event.pk]),
            event,
        )


@admin.register(EventBillingConfiguration)
class EventBillingConfigurationAdmin(ExtraChangeListLinksMixin, ModelAdmin):
    changelist_links = (
        AdminLink(
            _('All invoices'),
            icon='receipt',
            url_name='admin:billing_eventinvoice_changelist',
            permission='billing.view_eventinvoice',
        ),
    )
    list_display = (
        'event_link',
        'due_date',
        'integration_type',
        'price',
        'price_selector',
        'invoice_count',
        'ref_export',
    )
    list_filter = ('integration_type',)
    search_fields = ('event__title', 'event__slug', 'price_selector')
    autocomplete_fields = ('event',)
    list_select_related = ('event',)
    ordering = ('event',)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(invoice_total=Count('event__eventattendees__eventinvoice', distinct=True))
        )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            re_path(r'^(?P<conf_id>.+)/ref_numbers/$', self.ref_numbers, name='billing_ref_numbers'),
        ]
        return my_urls + urls

    @admin.display(description="Exportera data")
    def ref_export(self, obj):
        return format_html(
            '<a class="button" href="{}">Exportera data</a>&nbsp;',
            reverse('admin:billing_ref_numbers', args=[obj.pk]),
        )

    @admin.display(description=_('Event'))
    def event_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:events_event_change', args=[obj.event_id]),
            obj.event,
        )

    @admin.display(description=_('Invoices'))
    def invoice_count(self, obj):
        count = getattr(
            obj,
            'invoice_total',
            EventInvoice.objects.filter(participant__event=obj.event).count(),
        )
        if not count:
            return '0'
        return format_html(
            '<a href="{}?{}">{} {}</a>',
            reverse('admin:billing_eventinvoice_changelist'),
            urlencode({'participant__event__id__exact': obj.event_id}),
            count,
            ngettext('invoice', 'invoices', count),
        )

    def ref_numbers(self, request, conf_id):
        bconfig = self.get_object(request, conf_id)
        event = bconfig.event

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{event.title}_ref_numbers.csv"'},
        )

        if bconfig.integration_type == BillingIntegrations.INVOICE.value:
            invoices = EventInvoice.objects.filter(participant__event=event)
            fieldnames = [
                'name',
                'email',
                'invoice_number',
                'reference_number',
                'invoice_date',
                'due_date',
                'amount',
                'currency',
            ]
            writer = csv.DictWriter(response, fieldnames=fieldnames)
            writer.writeheader()
            for invoice in invoices:
                writer.writerow(
                    {
                        'name': invoice.participant.user,
                        'email': invoice.participant.email,
                        'invoice_number': invoice.invoice_number,
                        'reference_number': invoice.reference_number,
                        'invoice_date': invoice.invoice_date,
                        'due_date': invoice.due_date,
                        'amount': invoice.amount,
                        'currency': invoice.currency,
                    }
                )
        else:
            return HttpResponse("Integration not supported", 400)

        return response
