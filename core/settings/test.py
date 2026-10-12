from .date import *  # noqa
from core.translation_compiler import ensure_compiled_translations


ensure_compiled_translations()
PROJECT_NAME = "date"
ENABLE_LANGUAGE_FEATURES = True
LANGUAGES = ALL_LANGUAGES
# Pinned so the suite is deterministic whatever the environment holds: the
# shared settings read the secret from DATE_SECRET_KEY, which the
# docker-compose path supplies from .env. Anything derived from it (account
# activation tokens, the booking code) would otherwise change with the
# environment and pin a different value in CI than on a developer's machine.
SECRET_KEY = "SECRET_KEY"  # noqa: S105 (pinned test secret, never a real credential)
# Empty so validate_captcha fails open, which is the documented default for an
# association that has not configured Turnstile. Tests that need verification to
# happen enable it with override_settings(CAPTCHA_SITE_KEY=..., TURNSTILE_SECRET_KEY=...).
TURNSTILE_SECRET_KEY = ""
# Pinned so the suite is deterministic: this module inherits from date (where
# the capability is on by default) and CI copies .env.example to .env, so
# reading the environment here would make the tests depend on the developer's
# .env. Tests that need the capability off use @override_settings.
BOOKING_ENABLED = True

# Use in-memory sqlite database for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# No collected static in tests: resolve {% static %} to plain paths.
STORAGES = {
    **STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Use local memory cache to avoid Redis dependency during tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

OTP_WEBAUTHN_RP_ID = 'localhost'
OTP_WEBAUTHN_ALLOWED_ORIGINS = ['http://localhost:8000']
PASSKEYS_ENABLED = True
SILENCED_SYSTEM_CHECKS = []

LOGGING = {
    'version': 1,
    # Silence Django's default loggers explicitly: configure_logging applies
    # Django's DEFAULT_LOGGING first, which gives 'django' and 'django.server'
    # console handlers at INFO that the CRITICAL root level cannot gate.
    # Keep disable_existing_loggers=False: Django 6 re-runs
    # configure_logging() on every django.setup() call (e.g. when a test
    # module imports the ASGI application), and disabling existing loggers
    # would permanently disable loggers created at import time (like
    # 'date'), breaking assertLogs-based tests.
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        # Keep Django's own loggers quiet but not silent: a CRITICAL handler
        # still surfaces fatal framework errors, unlike dropping the loggers
        # entirely (no handler + no propagation swallows CRITICAL too).
        'django': {'level': 'CRITICAL', 'handlers': ['console'], 'propagate': False},
        'django.server': {'level': 'CRITICAL', 'handlers': ['console'], 'propagate': False},
    },
    'root': {
        'handlers': ['console'],
        'level': 'CRITICAL',
    },
}
