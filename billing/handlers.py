import datetime

from events.models import EventAttendees
from .models import EventInvoice, EventBillingConfiguration
from .util import BillingIntegrations, generate_reference_number, generate_invoice_number, get_selection_price, send_event_invoice


def handle_event_billing(signup: EventAttendees, retries=2):
    event = signup.event
    billing_config = EventBillingConfiguration.objects.get(event=event)
    if not billing_config:
        return

    provider = BillingIntegrations(billing_config.integration_type)

    if provider == BillingIntegrations.INVOICE:
        invoice_number = generate_invoice_number()
        amount = get_selection_price(event, billing_config.price, billing_config.price_selector, signup.preferences)
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
        except Exception as e:
            print(f"Failed to create invoice for {signup}: {e}")
            return handle_event_billing(signup, retries=retries-1)

        send_event_invoice(signup, invoice)
