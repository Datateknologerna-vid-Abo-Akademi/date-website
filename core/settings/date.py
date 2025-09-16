from .common import *  # noqa


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
    'jwt_auth',
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
