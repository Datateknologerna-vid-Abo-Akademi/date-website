import datetime
import logging

from events.models import EventAttendees
from .models import EventInvoice, EventBillingConfiguration
from .util import BillingIntegrations, generate_reference_number, generate_invoice_number, get_selection_price, send_event_invoice, send_event_free_confirmation


logger = logging.getLogger('date')


def handle_event_billing(signup: EventAttendees, retries=2):
    event = signup.original_event or signup.event
    try:
        billing_config = EventBillingConfiguration.objects.get(event=event)
    except EventBillingConfiguration.DoesNotExist:
        return
    if not billing_config:
        return

    provider = BillingIntegrations(billing_config.integration_type)

    if provider == BillingIntegrations.INVOICE:
        invoice_number = generate_invoice_number()
        amount = get_selection_price(event, billing_config.price, billing_config.price_selector, signup.preferences)
        logger.debug(f"Generated invoice number {invoice_number} with amount {amount}")
        if not amount:
            if amount == 0:
                send_event_free_confirmation(signup)
            return
        try:
            invoice = EventInvoice(
                participant=signup,
                invoice_number=invoice_number,
                reference_number=generate_reference_number(invoice_number),
                invoice_date=datetime.date.today(),
                due_date=billing_config.due_date,
                amount=amount,
            )
            invoice.save()
            
            # Send email with invoice
            send_event_invoice(signup, invoice)
        except Exception as e:
            logger.error(f"Failed to create invoice for {signup}: {e}")
            if retries:
                handle_event_billing(signup, retries=retries-1)
            return

