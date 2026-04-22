from .common import *  # noqa

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/sf',
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
    'publications',
    'alumni',
    'billing',
])

ROOT_URLCONF = 'core.urls.sf'

STAFF_GROUPS = get_staff_groups([
        'styrelse',
        'admin',
        'fotograf',
        'rösträknare'
    ])


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/sf'),
    os.path.join(BASE_DIR, 'static/common'),
]


CONTENT_VARIABLES = {
    "SITE_URL": "https://example.com",
    "ASSOCIATION_NAME": "SF-Klubben",
    "ASSOCIATION_NAME_FULL": "Statsvetenskapliga klubben vid Åbo Akademi r.f.",
    "ASSOCIATION_NAME_SHORT": "SF",
    "ASSOCIATION_EMAIL": "sf@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Porthansgatan 3",
    "ASSOCIATION_ADDRESS_L2": "Astra-huset våning 0, rum 0056",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "ASSOCIATION_OFFICE_HOURS": "Kanslitid mån-tors kl. 11.30-13.00",
    "SOCIAL_BUTTONS": [
        ["instagram", "https://www.instagram.com/sfklubben/"],
        ["facebook", "https://www.facebook.com/SFKlubben/"],
        ["x", "https://twitter.com/sfklubben"],
        ["linkedin", "https://linkedin.com/company/statsvetenskapligaklubben"],
    ],

    # Alumni
    "ALUMNI_ASSOCIATION_NAME": "",
    "ALUMNI_ASSOCIATION_NAME_SHORT": "",
    "ALUMNI_ASSOCIATION_EMAIL": "",

    # Events
    "INTERNATIONAL_EVENT_SLUGS": [],
}
