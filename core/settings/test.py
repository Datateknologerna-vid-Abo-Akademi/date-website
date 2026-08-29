from .date import *  # noqa
from core.translation_compiler import ensure_compiled_translations


ensure_compiled_translations()
PROJECT_NAME = "date"
ENABLE_LANGUAGE_FEATURES = True
LANGUAGES = ALL_LANGUAGES

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
        'django': {'level': 'CRITICAL', 'propagate': False},
        'django.server': {'level': 'CRITICAL', 'propagate': False},
    },
    'root': {
        'handlers': ['console'],
        'level': 'CRITICAL',
    },
}
