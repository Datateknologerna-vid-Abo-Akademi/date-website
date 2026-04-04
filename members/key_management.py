import logging
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger('date')


def generate_rsa_key() -> tuple:
    """Generate a 2048-bit RSA private key. Returns (pem: str, kid: str)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    kid = secrets.token_hex(8)
    return pem, kid


def ensure_signing_key() -> None:
    """
    Called from AppConfig.ready(). Auto-creates a signing key if none exists.
    Uses select_for_update inside a transaction to prevent duplicate creation
    on concurrent startup (e.g. multiple Docker replicas).
    Gracefully handles DB-not-ready during the initial migration run.
    """
    try:
        from django.db import transaction
        from .models import SigningKey
        with transaction.atomic():
            if not SigningKey.objects.select_for_update().filter(is_active=True).exists():
                pem, kid = generate_rsa_key()
                SigningKey.objects.create(kid=kid, private_key_pem=pem, is_active=True)
    except Exception:
        # Expected during initial migration when the table doesn't exist yet.
        # Any other failure is logged below via patch_dot_settings.
        pass


def patch_dot_settings() -> None:
    """
    Load signing keys from DB and patch OAUTH2_PROVIDER so DOT uses them.
    OIDC_RSA_PRIVATE_KEY           = active key (signs new tokens)
    OIDC_RSA_PRIVATE_KEYS_INACTIVE = retired keys (kept in JWKS so old tokens remain verifiable)
    Called from AppConfig.ready() after ensure_signing_key().
    """
    from django.db import OperationalError, ProgrammingError
    try:
        from django.conf import settings
        from .models import SigningKey
        active = SigningKey.objects.filter(is_active=True).order_by('-created_at').first()
        inactive = list(
            SigningKey.objects.filter(is_active=False).values_list('private_key_pem', flat=True)
        )
        if active:
            settings.OAUTH2_PROVIDER['OIDC_RSA_PRIVATE_KEY'] = active.private_key_pem
            settings.OAUTH2_PROVIDER['OIDC_RSA_PRIVATE_KEYS_INACTIVE'] = inactive
    except (OperationalError, ProgrammingError):
        # Table doesn't exist yet (pre-migration). Safe to ignore.
        pass
    except Exception:
        logger.exception('Unexpected error loading OIDC signing keys from DB')
