import random
from enum import Enum

import luhn

from events.models import EventRegistrationForm

class BillingIntegrations(Enum):
    """Integrations for billing"""
    INVOICE = 1


def generate_invoice_number() -> int:
    """Generate invoice number"""
    return random.randint(100000, 999999)


def generate_reference_number(invoice_number: int) -> str:
    """Generate reference number for invoice"""
    return luhn.append(str(invoice_number))


def get_selection_price(event, pricing, price_selector, preferences):
    """Get price based on selector"""
    if not price_selector:
        return float(pricing)
    options = EventRegistrationForm.objects.get(event=event, name=price_selector).choice_list.split(",")
    pricing_list = pricing.split(",")
    pricelist = [(option, float(pricing_list[i])) for option, i in enumerate(options)]
    for option, price in pricelist:
        if option == preferences[price_selector]:
            return float(price)
    raise ValueError("Price not found")
