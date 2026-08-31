from .common import *  # noqa

TEMPLATES = build_templates('date')

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
        'ctf',
        'publications',
        'alumni',
        'billing',
    ]
)

ROOT_URLCONF = 'core.urls.date'
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


STATICFILES_DIRS = build_static_dirs('date')

CONTENT_VARIABLES = {
    "SITE_URL": "https://datateknologerna.org",
    "ASSOCIATION_NAME": "Datateknologerna",
    "ASSOCIATION_NAME_FULL": "Datateknologerna vid Åbo Akademi rf",
    "ASSOCIATION_NAME_SHORT": "DaTe",
    "EVENT_TEMPLATE_LOGO": "core/images/headerlogo.png",
    "ASSOCIATION_EMAIL": "date@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Arken, B313",
    "ASSOCIATION_ADDRESS_L2": "Fabriksgatan 2",
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
    "INTERNATIONAL_EVENT_SLUGS": ["teekkarikaste_teknologdop"],
}

# Association capabilities
REGISTRATION_TERMS_ENABLED = True
EQUALITY_PLAN_ENABLED = True
