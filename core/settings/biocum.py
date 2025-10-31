from .common import *  # noqa


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/biocum',
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

INSTALLED_APPS = get_installed_apps([
    'staticpages',
    'news',
    'events',
    'ads',
    'social',
    'polls',
    'archive.apps.ArchiveConfig',
])

ROOT_URLCONF = 'core.urls.biocum'

STAFF_GROUPS = get_staff_groups([
        'styrelse',
        'admin',
        'fotograf',
        'rösträknare'
    ])

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/biocum'),
    os.path.join(BASE_DIR, 'static/common'),
]

CONTENT_VARIABLES = {
    "SITE_URL": "https://biologica.fi",
    "ASSOCIATION_NAME": "Biologica",
    "ASSOCIATION_NAME_FULL": "Biologica rf",
    "ASSOCIATION_NAME_SHORT": "Biologica",
    "ASSOCIATION_EMAIL": "biologica@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Biocity, 2:a vån",
    "ASSOCIATION_ADDRESS_L2": "Artillerigatan 6",
    "ASSOCIATION_POSTAL_CODE": "20520 ÅBO",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/Biologicarf/"],
        ["fa-instagram", "https://www.instagram.com/biologica_rf/"],
    ],
}
