from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, Warning


def check_passkey_settings(app_configs, **kwargs):
    if not settings.PASSKEYS_ENABLED:
        if settings.DEBUG:
            return []
        return [
            Warning(
                'Passkeys are disabled.',
                hint='Set WEBAUTHN_RP_ID and WEBAUTHN_ALLOWED_ORIGINS to enable passkey sign-in.',
                id='members.W001',
            )
        ]

    errors = []
    if not settings.CONTENT_VARIABLES.get('ASSOCIATION_NAME'):
        # py_webauthn rejects an empty RP name, which would 500 every registration.
        errors.append(
            Error(
                'Passkeys need a relying party name.',
                hint="Set CONTENT_VARIABLES['ASSOCIATION_NAME'] for this association.",
                id='members.E004',
            )
        )
    rp_id = settings.OTP_WEBAUTHN_RP_ID
    for origin in settings.OTP_WEBAUTHN_ALLOWED_ORIGINS:
        parts = urlsplit(origin)
        host = parts.hostname or ''
        if '*' in origin:
            errors.append(Error(f'Passkey origin {origin!r} must not contain wildcards.', id='members.E001'))
        # Browsers treat localhost as a secure context; any other host needs https.
        if parts.scheme != 'https' and host != 'localhost':
            errors.append(Error(f'Passkey origin {origin!r} must use https.', id='members.E002'))
        if host != rp_id and not host.endswith(f'.{rp_id}'):
            errors.append(
                Error(
                    f'Passkey origin {origin!r} is not on the relying party domain {rp_id!r}.',
                    hint='WEBAUTHN_RP_ID must equal, or be a parent domain of, every allowed origin host.',
                    id='members.E003',
                )
            )
    return errors
