from django.utils.translation import gettext_lazy as _

from .common import *  # noqa

TEMPLATES = build_templates('hf', parent_variants=('date',))

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
        'feedback',
        'publications',
        'billing',
        'klotterplanket',
    ]
)

ROOT_URLCONF = 'core.urls.hf'

STAFF_GROUPS = get_staff_groups(['styrelse', 'admin', 'webbansvarig'])


# Membership settings. Some of these are deliberately left at the shared
# defaults because the association has not supplied the real business values
# yet. A human must fill them in before launch:
#   MEMBERSHIP_SUBSCRIPTIONS: the membership fees and renewal periods. Left
#     unset, so no Subscription rows are provisioned and signup shows no
#     prices.
#   MEMBERS_SIGNUP_FIELDS: which fields the public signup form shows. Left
#     unset, so members.forms.MemberSignupForm keeps every model field.
#   ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY: whether archive access needs an
#     eligible membership. Left at the shared default (off).
#   MEMBER_ADMIN_RESTRICTED_GROUP and
#     MEMBER_ADMIN_RESTRICTED_MEMBERSHIP_TYPE: which group and membership
#     type are hidden from the member admin. Left at the shared defaults.
MEMBERSHIP_TYPE_NAMES = ('Ordinarie medlem',)
MEMBERS_SIGNUP_DEFAULT_MEMBERSHIP_TYPE = 'Ordinarie medlem'
MEMBERS_SIGNUP_CITY_LABEL = _('Hemort')

# Which permissions each staff group is provisioned with by
# members.provisioning.provision_membership_access(). The board deliberately
# gets everything except the members app, so it cannot touch member records.
# The setting keeps the name SF_ROLE_PERMISSION_SCOPES because
# members/provisioning.py reads that literal key for every association.
SF_ROLE_PERMISSION_SCOPES = {
    'styrelse': 'all_except_members',
    'webbansvarig': 'all',
    'admin': 'all',
}


STATICFILES_DIRS = build_static_dirs('hf')

CONTENT_VARIABLES = {
    "SITE_URL": "https://www.humanistiskaforeningen.com",
    "ASSOCIATION_NAME": "Humanistiska föreningen",
    "ASSOCIATION_NAME_FULL": "Humanistiska föreningen vid Åbo Akademi r.f.",
    "ASSOCIATION_NAME_SHORT": "HF",
    "ASSOCIATION_EMAIL": "hum@abo.fi",
    "ASSOCIATION_ADDRESS_L1": "Fabriksgatan 2",
    "ASSOCIATION_ADDRESS_L2": "",
    "ASSOCIATION_POSTAL_CODE": "20500 Åbo",
    # No office hours are published yet, on the association's site or anywhere
    # else, so this stays empty until someone supplies them.
    "ASSOCIATION_OFFICE_HOURS": "",
    # Names match the convention the shared footer expects: a platform with a
    # shared inline SVG under templates/common/core/svg/social/ is named bare
    # (tiktok), and a platform that falls back to the Line Awesome icon font
    # carries its own fa- prefix (fa-instagram, fa-facebook-f). A bare name
    # whose icon has no shared SVG renders an empty button, because the footer
    # then emits class="fab <name>".
    "SOCIAL_BUTTONS": [
        ["fa-instagram", "https://www.instagram.com/humanistiskaforeningen/"],
        ["fa-facebook-f", "https://www.facebook.com/HumanistiskaforeningenvidAA"],
        ["tiktok", "https://www.tiktok.com/@humanistiskaforeningen"],
    ],
    # Alumni
    "ALUMNI_ASSOCIATION_NAME": "",
    "ALUMNI_ASSOCIATION_NAME_SHORT": "",
    "ALUMNI_ASSOCIATION_EMAIL": "",
    # Events
    "INTERNATIONAL_EVENT_SLUGS": [],
}
