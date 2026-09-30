from django.utils.translation import gettext_lazy as _

from .common import *  # noqa

TEMPLATES = build_templates('sf', parent_variants=('date',))

INSTALLED_APPS = get_installed_apps(
    [
        'news',
        'gallery',
        'exambank',
        'archive.apps.ArchiveConfig',
        'events',
        'polls',
        'ads',
        'instagram',
        'harassment',
        'social',
        'staticpages',
        'publications',
        'billing',
        'klotterplanket',
    ]
)

ROOT_URLCONF = 'core.urls.sf'

STAFF_GROUPS = get_staff_groups(['styrelse', 'skattis', 'sekre', 'Inauta', 'webbansvarig', 'admin'])

MEMBERSHIP_TYPE_NAMES = ('Ordinarie medlem', 'Evig SF:are', 'Extra medlem')
MEMBERS_SIGNUP_FIELDS = (
    'username',
    'email',
    'first_name',
    'last_name',
    'city',
    'membership_type',
    'year_of_admission',
    'password',
)
MEMBERS_SIGNUP_DEFAULT_MEMBERSHIP_TYPE = 'Ordinarie medlem'
MEMBERS_SIGNUP_CITY_LABEL = _('Hemort')
MEMBERSHIP_SUBSCRIPTIONS = {
    'Ordinarie medlem': {
        'price': '15.00',
        'does_expire': True,
        'renewal_scale': 'year',
        'renewal_period': 1,
    },
    'Evig SF:are': {
        'price': '40.00',
        'does_expire': False,
        'renewal_scale': None,
        'renewal_period': None,
    },
    'Extra medlem': {
        'price': '15.00',
        'does_expire': True,
        'renewal_scale': 'year',
        'renewal_period': 1,
    },
}
ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY = True
MEMBER_ADMIN_RESTRICTED_GROUP = 'Inauta'
MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE = 'Evig SF:are'
SF_ROLE_PERMISSION_SCOPES = {
    'styrelse': 'all_except_members',
    'skattis': 'all',
    'sekre': 'all',
    'Inauta': 'all_with_lifetime_members',
    'webbansvarig': 'all',
    'admin': 'all',
}


STATICFILES_DIRS = build_static_dirs('sf')

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
