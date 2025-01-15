from .common import *  # noqa


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'templates/on',
            *COMMON_TEMPLATE_DIRS,
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                *COMMON_CONTEXT_PROCESSORS,
                # Add project context processors here
                "billing.context_processors.billing_context",
            ],
        },
    },
]

INSTALLED_APPS = get_installed_apps([
    'ads',
    'news',
    'social',
    'events',
    'billing',
    'staticpages',
    'archive.apps.ArchiveConfig',
])

ROOT_URLCONF = 'core.urls.on'

STAFF_GROUPS = get_staff_groups([
    'admin',
])


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/on'),
    os.path.join(BASE_DIR, 'static/common'),
]


CONTENT_VARIABLES = {
    "SITE_URL": "https://demo.datateknologerna.org",
    "ASSOCIATION_NAME": "ÖN Evenemang",
    "ASSOCIATION_NAME_FULL": "Österbottniska Nationens Årsfestkommité",
    "ASSOCIATION_NAME_SHORT": "ÖN Events",
    "ASSOCIATION_EMAIL": "onarsfest@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "c/o Kåren",
    "ASSOCIATION_ADDRESS_L2": "Tavastgatan 22",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "SOCIAL_BUTTONS": [
    ],
}

BILLING_CONTEXT = {
    "INVOICE_RECIPIENT": "Österbottniska Nationen vid Åbo Akademi r.f.",
    "IBAN": "FI35 5670 0820 4600 85",
    "BIC": "OKOYFIHH",
}
