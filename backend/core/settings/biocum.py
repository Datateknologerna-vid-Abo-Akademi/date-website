from .common import *  # noqa
from .validation import validate_association_settings


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            template_path('templates', 'biocum'),
            template_path('templates', 'date'),
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

ASSOCIATION_THEME = {
    "brand": "biocum",
    "font_heading": "DM Serif Display",
    "font_body": "Nunito Sans",
    "palette": {
        "background": "#f2f8f4",
        "surface": "#ffffff",
        "text": "#1b4332",
        "text_muted": "#52796f",
        "primary": "#2d6a4f",
        "secondary": "#84a98c",
        "accent": "#bc4749",
        "border": "#d8f3dc",
    },
}

try:
    theme_env = os.environ.get("ASSOCIATION_THEME", "{}").strip(' "\'')
    ASSOCIATION_THEME = {
        **ASSOCIATION_THEME,
        **json.loads(theme_env),
    }
except Exception:
    pass


validate_association_settings("core.settings.biocum", globals())
