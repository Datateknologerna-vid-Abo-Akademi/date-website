import random
from enum import Enum

from django.conf import settings
from django.template.loader import render_to_string

from billing.models import EventInvoice
from events.models import EventRegistrationForm, EventAttendees
from core.utils import send_email_task


class BillingIntegrations(Enum):
    """Integrations for billing"""
    INVOICE = 1


def generate_invoice_number() -> int:
    """Generate invoice number"""
    return random.randint(24000000, 24099999)


def generate_reference_number(invoice_number: int) -> str:
    """Generate reference number for invoice"""
    multiplication_feed = (7, 3, 1)
    reference_number_raw = str(invoice_number).replace(' ', '')
    numbers_reverse = map(int, reference_number_raw[::-1])
    sum_of_multiplication = sum(multiplication_feed[i % 3] * x for i, x in enumerate(numbers_reverse))
    return str(invoice_number)+str((10 - (sum_of_multiplication % 10)) % 10)


def get_selection_price(event, pricing, price_selector, preferences):
    """Get price based on selector"""
    if not price_selector:
        try:
            return float(pricing)
        except ValueError:
            return
    try:
        options = EventRegistrationForm.objects.get(event=event, name=price_selector).choice_list.split(",")
    except EventRegistrationForm.DoesNotExist:
        try:
            return float(pricing)
        except ValueError:
            return
    pricing_list = pricing.split(",")
    pricelist = [(option, float(pricing_list[i])) for i, option in enumerate(options)]
    for option, price in pricelist:
        if option == preferences[price_selector]:
            return float(price)
    raise ValueError("Price not found")


def send_event_invoice(signup: EventAttendees, invoice: EventInvoice):
    """Send invoice to participant"""
    context = {
        'invoice': invoice,
        'signup': signup,
        **settings.BILLING_CONTEXT,
        **settings.CONTENT_VARIABLES,
    }
    content = render_to_string('billing/invoice_email.txt', context)
    send_email_task.delay(f"{signup.event.title} - Betalningsuppgifter", content, settings.DEFAULT_FROM_EMAIL, [signup.email])


def send_event_free_confirmation(signup: EventAttendees):
    """Send confirmation email for free events"""
    context = {
        'signup': signup,
        **settings.BILLING_CONTEXT,
        **settings.CONTENT_VARIABLES,
    }
    content = render_to_string('billing/free_event_confirmation_email.txt', context)
    send_email_task.delay(f"{signup.event.title} - Bekräftelse", content, settings.DEFAULT_FROM_EMAIL, [signup.email])
