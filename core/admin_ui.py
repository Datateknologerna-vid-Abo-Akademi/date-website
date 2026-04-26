from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class AdminLink:
    label: str
    icon: str = ''
    url_name: str = ''
    url: str = ''
    permission: str = ''

    def resolve(self, request):
        if self.permission and not request.user.has_perm(self.permission):
            return None

        href = self.url
        if self.url_name:
            try:
                href = reverse(self.url_name)
            except NoReverseMatch:
                return None

        if not href:
            return None

        return {
            'href': href,
            'icon': self.icon,
            'label': self.label,
        }


TOPBAR_QUICK_CREATE_LINKS = (
    AdminLink(_('Event'), icon='event', url_name='admin:events_event_add', permission='events.add_event'),
    AdminLink(_('News'), icon='article', url_name='admin:news_post_add', permission='news.add_post'),
    AdminLink(_('Static Page'), icon='web', url_name='admin:staticpages_staticpage_add', permission='staticpages.add_staticpage'),
)


def resolve_admin_links(items, request):
    return [
        link
        for item in items
        if (link := item.resolve(request)) is not None
    ]


def get_topbar_quick_create_links(request):
    return resolve_admin_links(TOPBAR_QUICK_CREATE_LINKS, request)


@dataclass(frozen=True)
class AdminSidebarGroup:
    title: str
    items: tuple[AdminLink, ...]
    separator: bool = True

    def resolve(self, request):
        items = [
            {
                'title': link['label'],
                'icon': link['icon'],
                'link': link['href'],
            }
            for item in self.items
            if (link := item.resolve(request)) is not None
        ]
        if not items:
            return None
        return {
            'title': self.title,
            'separator': self.separator,
            'items': items,
        }


SIDEBAR_NAVIGATION = (
    AdminSidebarGroup(_('Events'), (
        AdminLink(_('Events'), icon='event', url_name='admin:events_event_changelist', permission='events.view_event'),
        AdminLink(_('Billing Configuration'), icon='receipt_long', url_name='admin:billing_eventbillingconfiguration_changelist', permission='billing.view_eventbillingconfiguration'),
        AdminLink(_('Invoices'), icon='receipt', url_name='admin:billing_eventinvoice_changelist', permission='billing.view_eventinvoice'),
    )),
    AdminSidebarGroup(_('Members'), (
        AdminLink(_('Members'), icon='group', url_name='admin:members_member_changelist', permission='members.view_member'),
        AdminLink(_('Membership Types'), icon='badge', url_name='admin:members_membershiptype_changelist', permission='members.view_membershiptype'),
        AdminLink(_('Subscriptions'), icon='card_membership', url_name='admin:members_subscription_changelist', permission='members.view_subscription'),
        AdminLink(_('Subscription Payments'), icon='payments', url_name='admin:members_subscriptionpayment_changelist', permission='members.view_subscriptionpayment'),
        AdminLink(_('Functionaries'), icon='manage_accounts', url_name='admin:members_functionary_changelist', permission='members.view_functionary'),
        AdminLink(_('Functionary Roles'), icon='work', url_name='admin:members_functionaryrole_changelist', permission='members.view_functionaryrole'),
    )),
    AdminSidebarGroup(_('Content'), (
        AdminLink(_('News'), icon='article', url_name='admin:news_post_changelist', permission='news.view_post'),
        AdminLink(_('News Categories'), icon='category', url_name='admin:news_category_changelist', permission='news.view_category'),
        AdminLink(_('Polls'), icon='poll', url_name='admin:polls_question_changelist', permission='polls.view_question'),
        AdminLink(_('Static Pages'), icon='web', url_name='admin:staticpages_staticpage_changelist', permission='staticpages.view_staticpage'),
        AdminLink(_('Page Navigation'), icon='menu_book', url_name='admin:staticpages_staticpagenav_changelist', permission='staticpages.view_staticpagenav'),
    )),
    AdminSidebarGroup(_('Archive & Publications'), (
        AdminLink(_('PDF Publications'), icon='picture_as_pdf', url_name='admin:publications_pdffile_changelist', permission='publications.view_pdffile'),
        AdminLink(_('Photo Albums'), icon='photo_library', url_name='admin:archive_picturecollection_changelist', permission='archive.view_picturecollection'),
        AdminLink(_('Documents'), icon='folder', url_name='admin:archive_documentcollection_changelist', permission='archive.view_documentcollection'),
        AdminLink(_('Exams'), icon='school', url_name='admin:archive_examcollection_changelist', permission='archive.view_examcollection'),
    )),
    AdminSidebarGroup(_('Activities'), (
        AdminLink(_('CTF'), icon='military_tech', url_name='admin:ctf_ctf_changelist', permission='ctf.view_ctf'),
        AdminLink(_('CTF Guesses'), icon='flag', url_name='admin:ctf_guess_changelist', permission='ctf.view_guess'),
        AdminLink(_('Lucia'), icon='stars', url_name='admin:lucia_candidate_changelist', permission='lucia.view_candidate'),
    )),
    AdminSidebarGroup(_('Social & Ads'), (
        AdminLink(_('Samarbetspartners'), icon='campaign', url_name='admin:ads_adurl_changelist', permission='ads.view_adurl'),
        AdminLink(_('Instagram URLs'), icon='photo_camera', url_name='admin:social_igurl_changelist', permission='social.view_igurl'),
        AdminLink(_('Harassment Reports'), icon='report', url_name='admin:social_harassment_changelist', permission='social.view_harassment'),
        AdminLink(_('Report Recipients'), icon='mail', url_name='admin:social_harassmentemailrecipient_changelist', permission='social.view_harassmentemailrecipient'),
    )),
    AdminSidebarGroup(_('System'), (
        AdminLink(_('Admin Log'), icon='history', url_name='admin:admin_logentry_changelist', permission='admin.view_logentry'),
        AdminLink(_('Permissions'), icon='lock', url_name='admin:auth_permission_changelist', permission='auth.view_permission'),
    )),
)


def get_sidebar_navigation(request):
    return [
        group
        for item in SIDEBAR_NAVIGATION
        if (group := item.resolve(request)) is not None
    ]
