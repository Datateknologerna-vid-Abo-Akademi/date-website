import os

from .common import *  # noqa

TEMPLATES = build_templates('demo')

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
        'feedback',
    ]
)

ROOT_URLCONF = 'core.urls.demo'

STAFF_GROUPS = get_staff_groups(['styrelse', 'admin', 'fotograf', 'rösträknare'])


STATICFILES_DIRS = build_static_dirs('demo')

CONTENT_VARIABLES = {
    "SITE_URL": "https://demo.datateknologerna.org",
    "ASSOCIATION_NAME": "DaTe demo",
    "ASSOCIATION_NAME_FULL": "Demo Website",
    "ASSOCIATION_NAME_SHORT": "Demo",
    "EVENT_TEMPLATE_LOGO": "core/images/headerlogo.png",
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

# Lunch widget fallback coordinates for the association kansli (Agora, Vattenborgsvägen 5).
LUNCH_KANSLI_LATITUDE = 60.4555079
LUNCH_KANSLI_LONGITUDE = 22.285437
LUNCH_LAT = env('LUNCH_LAT', float, LUNCH_KANSLI_LATITUDE) if os.environ.get('LUNCH_LAT') else LUNCH_KANSLI_LATITUDE
LUNCH_LNG = env('LUNCH_LNG', float, LUNCH_KANSLI_LONGITUDE) if os.environ.get('LUNCH_LNG') else LUNCH_KANSLI_LONGITUDE
