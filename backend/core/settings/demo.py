from .common import *  # noqa
from .validation import validate_association_settings


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            template_path('templates', 'demo'),
            *COMMON_TEMPLATE_DIRS,
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                *COMMON_CONTEXT_PROCESSORS,
                # Add project context processors here
            ],
        },
    },
]

INSTALLED_APPS = get_installed_apps([
    'news',
    'archive.apps.ArchiveConfig',
    'events',
    'polls',
    'ads',
    'social',
    'staticpages',
])

ROOT_URLCONF = 'core.urls.demo'

STAFF_GROUPS = get_staff_groups([
    'styrelse',
    'admin',
    'fotograf',
    'rösträknare'
])


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/demo'),
    os.path.join(BASE_DIR, 'static/common'),
]


CONTENT_VARIABLES = {
    "SITE_URL": "https://demo.datateknologerna.org",
    "ASSOCIATION_NAME": "DaTe demo",
    "ASSOCIATION_NAME_FULL": "Demo Website",
    "ASSOCIATION_NAME_SHORT": "Demo",
    "ASSOCIATION_EMAIL": "demo@datateknologerna.org",
    "ASSOCIATION_ADDRESS_L1": "Åbo Akademi, Agora",
    "ASSOCIATION_ADDRESS_L2": "Vattenborgsvägen 5",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/HerrKanin/"],
        ["fa-instagram", "https://www.instagram.com/datateknologerna/"],
        ["fa-linkedin-in", "https://www.linkedin.com/company/datateknologerna-vid-%C3%A5bo-akademi-rf/"],
        ["fa-github", "https://github.com/Datateknologerna-vid-Abo-Akademi"],
    ],
}

ASSOCIATION_THEME = {
    "brand": "demo",
    "font_heading": "Prata",
    "font_body": "Hind",
    "palette": {
        "background": "#f6f7fb",
        "surface": "#ffffff",
        "text": "#111827",
        "text_muted": "#4b5563",
        "primary": "#334155",
        "secondary": "#f59e0b",
        "accent": "#0ea5e9",
        "border": "#d1d5db",
    },
}

try:
    ASSOCIATION_THEME = {
        **ASSOCIATION_THEME,
        **json.loads(os.environ.get("ASSOCIATION_THEME", "{}")),
    }
except Exception:
    pass


validate_association_settings("core.settings.demo", globals())
