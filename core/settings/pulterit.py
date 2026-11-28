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

# The lunchmenu.fi student lunch widget follows the place it searches from.
# Pulterit points it at Kåren (Hämeenkatu 22) and asks for one restaurant, so
# the widget lists Kåren alone with its student prices. There is no /lunch page:
# the widget sits on the homepage only.
KAREN_LATITUDE = 60.4495319
KAREN_LONGITUDE = 22.2756869
LUNCH_ENABLED = env('LUNCH_ENABLED', bool, True)
LUNCH_LAT = env('LUNCH_LAT', float, KAREN_LATITUDE) if os.environ.get('LUNCH_LAT') else KAREN_LATITUDE
LUNCH_LNG = env('LUNCH_LNG', float, KAREN_LONGITUDE) if os.environ.get('LUNCH_LNG') else KAREN_LONGITUDE
LUNCH_COUNT = env('LUNCH_COUNT', int, 1)
# The widget's link and price colour: the site's own link colour.
LUNCH_ACCENT = env('LUNCH_ACCENT', str, '#6d6d69')
