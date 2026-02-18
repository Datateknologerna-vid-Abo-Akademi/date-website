from .common import *  # noqa
from .validation import validate_association_settings


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/date',
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
    'ctf',
    'publications',
    'alumni',
    'billing',
])

ROOT_URLCONF = 'core.urls.date'

STAFF_GROUPS = get_staff_groups([
        'styrelse',
        'admin',
        'fotograf',
        'rösträknare'
    ])


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/date'),
    os.path.join(BASE_DIR, 'static/common'),
]


CONTENT_VARIABLES = {
    "SITE_URL": "https://datateknologerna.org",
    "ASSOCIATION_NAME": "Datateknologerna",
    "ASSOCIATION_NAME_FULL": "Datateknologerna vid Åbo Akademi rf",
    "ASSOCIATION_NAME_SHORT": "DaTe",
    "ASSOCIATION_EMAIL": "date@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Åbo Akademi, Agora",
    "ASSOCIATION_ADDRESS_L2": "Vattenborgsvägen 5",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/HerrKanin/"],
        ["fa-instagram", "https://www.instagram.com/datateknologerna/"],
        ["fa-linkedin-in", "https://www.linkedin.com/company/datateknologerna-vid-%C3%A5bo-akademi-rf/"],
        ["fa-github", "https://github.com/Datateknologerna-vid-Abo-Akademi"],
    ],

    # Alumni
    "ALUMNI_ASSOCIATION_NAME": "Albins R Gamyler",
    "ALUMNI_ASSOCIATION_NAME_SHORT": "ARG",
    "ALUMNI_ASSOCIATION_EMAIL": "arg@datateknologerna.org",

    # Events
    "INTERNATIONAL_EVENT_SLUGS": [
        "teekkarikaste_teknologdop"
    ],
}

ASSOCIATION_THEME = {
    "brand": "date",
    "font_heading": "Bree Serif",
    "font_body": "Libre Franklin",
    "palette": {
        "background": "#f8f6f2",
        "surface": "#ffffff",
        "text": "#1f2937",
        "text_muted": "#4b5563",
        "primary": "#6d1f2f",
        "secondary": "#d4a017",
        "accent": "#2a9d8f",
        "border": "#e5e7eb",
    },
}

try:
    ASSOCIATION_THEME = {
        **ASSOCIATION_THEME,
        **json.loads(os.environ.get("ASSOCIATION_THEME", "{}")),
    }
except Exception:
    pass


validate_association_settings("core.settings.date", globals())
