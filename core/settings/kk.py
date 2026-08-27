from .common import *  # noqa

TEMPLATES = build_templates('kk')

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
        'lucia',
        'publications',
        'alumni',
        'billing',
    ]
)

ROOT_URLCONF = 'core.urls.kk'
USE_ACCEPT_LANGUAGE_HEADER = False

STAFF_GROUPS = get_staff_groups(['styrelse', 'admin', 'fotograf', 'rösträknare'])


STATICFILES_DIRS = build_static_dirs('kk')

CONTENT_VARIABLES = {
    "SITE_URL": "https://kemistklubben.org",
    "ASSOCIATION_NAME": "Kemistklubben",
    "ASSOCIATION_NAME_FULL": "Kemistklubben vid Åbo Akademi rf",
    "ASSOCIATION_NAME_SHORT": "KK",
    "EVENT_TEMPLATE_LOGO": "core/images/headerlogo.png",
    "ASSOCIATION_EMAIL": "kk@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Åbo Akademi, Aurum",
    "ASSOCIATION_ADDRESS_L2": "Henriksgatan 2",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    "ASSOCIATION_OFFICE_HOURS": "Kanslitid Må - To 11:30-13",
    "SOCIAL_BUTTONS": [
        ["fa-facebook-f", "https://www.facebook.com/kemistklubbenvidaboakademi/"],
        ["fa-instagram", "https://www.instagram.com/kemistklubben/"],
        ["fa-linkedin-in", "https://www.linkedin.com/company/kemistklubben-vid-%C3%A5bo-akademi-rf/"],
    ],
    # Alumni
    "ALUMNI_ASSOCIATION_NAME": "Axels och Stinas Gamyler",
    "ALUMNI_ASSOCIATION_NAME_SHORT": "ASG",
    "ALUMNI_ASSOCIATION_EMAIL": "asg@kemistklubben.org",
}
