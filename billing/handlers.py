import datetime

from events.models import EventAttendees
from .models import EventInvoice, EventBillingConfiguration
from util import BillingIntegrations, generate_reference_number, generate_invoice_number, get_selection_price

def handle_event_billing(signup: EventAttendees):
    event = signup.event
    billing_config = EventBillingConfiguration.objects.get(event=event)
    if not billing_config:
        return

    provider = BillingIntegrations(billing_config.integration_type)

    if provider == BillingIntegrations.INVOICE:
        invoice_number = generate_invoice_number()
        amount = get_selection_price(event, billing_config.price, billing_config.price_selector, signup.preferences)
        invoice = EventInvoice(
            participant=signup,
            invoice_number=invoice_number,
            reference_number=generate_reference_number(invoice_number),
            invoice_date=datetime.date.today(),
            due_date=billing_config.due_date,
            amount=amount,
        )
        invoice.save()
