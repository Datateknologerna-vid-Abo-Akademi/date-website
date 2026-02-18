from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from core.settings.validation import validate_association_settings


def make_valid_namespace():
    return {
        "CONTENT_VARIABLES": {
            "SITE_URL": "https://example.org",
            "ASSOCIATION_NAME": "Example Association",
            "ASSOCIATION_NAME_SHORT": "EA",
            "ASSOCIATION_EMAIL": "board@example.org",
            "SOCIAL_BUTTONS": [
                ["fa-facebook-f", "https://facebook.com/example"],
            ],
        },
        "ASSOCIATION_THEME": {
            "brand": "example",
            "font_heading": "Playfair Display",
            "font_body": "Public Sans",
            "palette": {
                "background": "#ffffff",
                "surface": "#f8f8f8",
                "text": "#111111",
                "text_muted": "#333333",
                "primary": "#005577",
                "secondary": "#aabb00",
                "accent": "#992211",
                "border": "#dddddd",
            },
        },
        "FRONTEND_DEFAULT_ROUTE": "/events",
        "EXPERIMENTAL_FEATURES": [],
        "INSTALLED_APPS": ["events", "news"],
    }


class ValidateAssociationSettingsTests(SimpleTestCase):
    def test_valid_namespace_passes(self):
        namespace = make_valid_namespace()
        validate_association_settings("core.settings.example", namespace)

    def test_invalid_frontend_route_raises(self):
        namespace = make_valid_namespace()
        namespace["FRONTEND_DEFAULT_ROUTE"] = "events"
        with self.assertRaises(ImproperlyConfigured):
            validate_association_settings("core.settings.example", namespace)

    def test_missing_theme_palette_key_raises(self):
        namespace = make_valid_namespace()
        del namespace["ASSOCIATION_THEME"]["palette"]["primary"]
        with self.assertRaises(ImproperlyConfigured):
            validate_association_settings("core.settings.example", namespace)

    def test_event_billing_requires_billing_context(self):
        namespace = make_valid_namespace()
        namespace["EXPERIMENTAL_FEATURES"] = ["event_billing"]
        namespace["INSTALLED_APPS"] = ["events", "billing"]
        with self.assertRaises(ImproperlyConfigured):
            validate_association_settings("core.settings.example", namespace)

    def test_event_billing_passes_with_billing_context(self):
        namespace = make_valid_namespace()
        namespace["EXPERIMENTAL_FEATURES"] = ["event_billing"]
        namespace["INSTALLED_APPS"] = ["events", "billing"]
        namespace["BILLING_CONTEXT"] = {
            "INVOICE_RECIPIENT": "Example Association",
            "IBAN": "FI00 0000 0000 0000 00",
            "BIC": "AAAAFIHH",
        }
        validate_association_settings("core.settings.example", namespace)
