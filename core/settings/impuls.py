from .common import *  # noqa

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/impuls',
            'templates/date',
            *COMMON_TEMPLATE_DIRS,
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                *COMMON_CONTEXT_PROCESSORS,
            ],
        },
    },
]

INSTALLED_APPS = get_installed_apps(
    [
        'news',
        'gallery',
        'exambank',
        'archive',
        'events',
        'polls',
        'ads',
        'instagram',
        'harassment',
        'social',
        'staticpages',
        'publications',
        'alumni',
        'billing',
    ]
)

ROOT_URLCONF = 'core.urls.impuls'
USE_ACCEPT_LANGUAGE_HEADER = False
DATE_LANGUAGES = (
    ("sv", "Svenska"),
    ("en", "English"),
)
LANGUAGES = (
    DATE_LANGUAGES
    if ENABLE_LANGUAGE_FEATURES
    else tuple(language for language in DATE_LANGUAGES if language[0] == LANGUAGE_CODE)
)

STAFF_GROUPS = get_staff_groups(['styrelse', 'admin', 'fotograf', 'rösträknare'])

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/impuls'),
    os.path.join(BASE_DIR, 'static/common'),
]

CONTENT_VARIABLES = {
    "SITE_URL": "https://example.com",
    "ASSOCIATION_NAME": "Impuls",
    "ASSOCIATION_NAME_FULL": "Impuls",
    "ASSOCIATION_NAME_SHORT": "Impuls",
    "EVENT_TEMPLATE_LOGO": "core/images/impuls-logo.png",
    "ASSOCIATION_EMAIL": "impuls@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Åbo Akademi",
    "ASSOCIATION_ADDRESS_L2": "Fabriksgatan 2",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/Impulsrf/"],
        ["fa-instagram", "https://www.instagram.com/impulsrf/"],
    ],
    # Alumni
    "ALUMNI_ASSOCIATION_NAME": "",
    "ALUMNI_ASSOCIATION_NAME_SHORT": "",
    "ALUMNI_ASSOCIATION_EMAIL": "",
    # Events
    "INTERNATIONAL_EVENT_SLUGS": [],
}
