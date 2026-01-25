from .common import *  # noqa


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/pulterit',
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
    'publications',
    'billing',
])

ROOT_URLCONF = 'core.urls.pulterit'

STAFF_GROUPS = get_staff_groups([
        'styrelse',
        'admin',
        'fotograf',
        'rösträknare'
    ])


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/pulterit'),
    os.path.join(BASE_DIR, 'static/common'),
]


CONTENT_VARIABLES = {
    "SITE_URL": "https://pulterit.org",
    "ASSOCIATION_NAME": "Pulterit",
    "ASSOCIATION_NAME_FULL": "Pulterit ry",
    "ASSOCIATION_NAME_SHORT": "Pulterit",
    "ASSOCIATION_EMAIL": "pulterithal@utu.fi",
    "ASSOCIATION_ADDRESS_L1": "Geotalo / Geohuset / Geohouse",
    "ASSOCIATION_ADDRESS_L2": "Akatemiankatu 1",
    "ASSOCIATION_POSTAL_CODE": "20500 Turku",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/pulterit/"],
        ["fa-instagram", "https://www.instagram.com/pulteritry/"],
        ["fa-linkedin-in", ""],
        ["fa-github", ""],
    ],
}
