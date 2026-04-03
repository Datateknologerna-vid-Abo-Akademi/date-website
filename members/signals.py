from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .constants import (
    TWO_FACTOR_SETUP_SESSION_KEY,
    TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY,
)


@receiver(user_logged_in)
def reset_two_factor_verification(sender, request, user, **kwargs):
    if request is None:
        return
    request.session.pop(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, None)
    request.session.pop(TWO_FACTOR_SETUP_SESSION_KEY, None)


@receiver(user_logged_out)
def clear_two_factor_verification(sender, request, user, **kwargs):
    if request is None:
        return
    request.session.pop(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, None)
    request.session.pop(TWO_FACTOR_SETUP_SESSION_KEY, None)
