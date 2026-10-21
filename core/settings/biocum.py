import os

from .common import *  # noqa

TEMPLATES = build_templates('biocum', parent_variants=('date',))

INSTALLED_APPS = get_installed_apps(
    [
        'staticpages',
        'feedback',
        'news',
        'events',
        'ads',
        'instagram',
        'harassment',
        'social',
        'polls',
        'gallery',
        'exambank',
        'archive',
        'publications',
    ]
)

ROOT_URLCONF = 'core.urls.biocum'
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

STATICFILES_DIRS = build_static_dirs('biocum')

CONTENT_VARIABLES = {
    "SITE_URL": "https://biologica.fi",
    "ASSOCIATION_NAME": "Biologica",
    "ASSOCIATION_NAME_FULL": "Biologica rf",
    "ASSOCIATION_NAME_SHORT": "Biologica",
    "EVENT_TEMPLATE_LOGO": "core/images/headerlogo.png",
    "ASSOCIATION_EMAIL": "biologica@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Biocity, 2:a vån",
    "ASSOCIATION_ADDRESS_L2": "Artillerigatan 6",
    "ASSOCIATION_POSTAL_CODE": "20520 ÅBO",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/Biologicarf/"],
        ["fa-instagram", "https://www.instagram.com/biologica_rf/"],
    ],
}

# Lunch widget fallback coordinates for the association kansli (Biocity, Artillerigatan 6).
LUNCH_KANSLI_LATITUDE = 60.4493152
LUNCH_KANSLI_LONGITUDE = 22.2932317
LUNCH_LAT = env('LUNCH_LAT', float, LUNCH_KANSLI_LATITUDE) if os.environ.get('LUNCH_LAT') else LUNCH_KANSLI_LATITUDE
LUNCH_LNG = env('LUNCH_LNG', float, LUNCH_KANSLI_LONGITUDE) if os.environ.get('LUNCH_LNG') else LUNCH_KANSLI_LONGITUDE
