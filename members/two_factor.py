import base64
import io

import pyotp
import qrcode
from django.conf import settings


def generate_two_factor_secret():
    return pyotp.random_base32()


def normalize_token(token):
    return "".join(character for character in token if character.isdigit())


def verify_two_factor_token(secret, token):
    normalized_token = normalize_token(token)
    if not secret or len(normalized_token) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(normalized_token, valid_window=0)


def build_totp_provisioning_uri(user, secret):
    issuer = getattr(settings, "TWO_FACTOR_ISSUER_NAME", settings.PROJECT_NAME.upper())
    return pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=issuer)


def build_qr_code_data_uri(data):
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{image_data}"
