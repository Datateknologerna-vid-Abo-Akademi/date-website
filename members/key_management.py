import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


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
    Gracefully handles the case where migrations haven't run yet.
    """
    try:
        from .models import SigningKey
        if not SigningKey.objects.filter(is_active=True).exists():
            pem, kid = generate_rsa_key()
            SigningKey.objects.create(kid=kid, private_key_pem=pem, is_active=True)
    except Exception:
        # DB not ready (first migration run, test setup, etc.) — silently skip
        pass


def patch_dot_settings() -> None:
    """
    Load signing keys from DB and patch OAUTH2_PROVIDER so DOT uses them.
    OIDC_RSA_PRIVATE_KEY         = active key (used to sign new tokens)
    OIDC_RSA_PRIVATE_KEYS_INACTIVE = inactive keys (kept in JWKS for verification)
    Called from AppConfig.ready() after ensure_signing_key().
    """
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
    except Exception:
        pass
