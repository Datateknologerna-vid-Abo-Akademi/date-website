from django.conf import settings


def billing_context(_):
    return settings.BILLING_CONTEXT
