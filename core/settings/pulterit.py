import os

from .common import *  # noqa

TEMPLATES = build_templates('pulterit')

INSTALLED_APPS = get_installed_apps(
    [
        'news',
        'events',
        'polls',
        'ads',
        'instagram',
        'harassment',
        'social',
        'staticpages',
        'feedback',
        'exambank',
        'publications',
        'billing',
    ]
)

ROOT_URLCONF = 'core.urls.pulterit'
ARCHIVE_ENABLED = False
MEMBERS_SIGNUP_ENABLED = False
# Pulterit has no member accounts to sign in with, so the public functionaries
# listing must honour the year and role filters for signed-out visitors.
FUNCTIONARIES_ANONYMOUS_FILTERS = True

STAFF_GROUPS = get_staff_groups(['styrelse', 'admin', 'fotograf', 'rösträknare'])


STATICFILES_DIRS = build_static_dirs('pulterit')

CONTENT_VARIABLES = {
    "SITE_URL": "https://pulterit.org",
    "ASSOCIATION_NAME": "Pulterit",
    "ASSOCIATION_NAME_FULL": "Pulterit ry",
    "ASSOCIATION_NAME_FULL_RF": "Pulterit rf",
    "ASSOCIATION_NAME_SHORT": "Pulterit",
    "EVENT_TEMPLATE_LOGO": "core/images/pulterit-black-wo-text.svg",
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

# Lunch widget fallback coordinates for the association kansli (Geohuset, Akatemiankatu 1).
LUNCH_KANSLI_LATITUDE = 60.4510752
LUNCH_KANSLI_LONGITUDE = 22.2788933
LUNCH_LAT = env('LUNCH_LAT', float, LUNCH_KANSLI_LATITUDE) if os.environ.get('LUNCH_LAT') else LUNCH_KANSLI_LATITUDE
LUNCH_LNG = env('LUNCH_LNG', float, LUNCH_KANSLI_LONGITUDE) if os.environ.get('LUNCH_LNG') else LUNCH_KANSLI_LONGITUDE
