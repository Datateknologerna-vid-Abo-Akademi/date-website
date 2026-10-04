from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class AdminLink:
    label: str | Promise
    icon: str = ''
    url_name: str = ''
    url: str = ''
    permission: str = ''
    any_permissions: tuple[str, ...] = ()

    @staticmethod
    def _has_permission(user, permission):
        if user.has_perm(permission):
            return True
        app_label, codename = permission.split('.', 1)
        if codename.startswith('view_'):
            return user.has_perm(f'{app_label}.change_{codename.removeprefix("view_")}')
        return False

    def resolve(self, request):
        if self.permission and not self._has_permission(request.user, self.permission):
            return None
        if self.any_permissions and not any(
            self._has_permission(request.user, permission) for permission in self.any_permissions
        ):
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


def resolve_admin_links(items, request):
    return [link for item in items if (link := item.resolve(request)) is not None]


@dataclass(frozen=True)
class AdminSidebarGroup:
    title: str | Promise
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
    AdminSidebarGroup(
        _('Events'),
        (
            AdminLink(
                _('Events'), icon='event', url_name='admin:events_event_changelist', permission='events.view_event'
            ),
            AdminLink(
                _('Billing Configuration'),
                icon='receipt_long',
                url_name='admin:billing_eventbillingconfiguration_changelist',
                permission='billing.view_eventbillingconfiguration',
            ),
        ),
    ),
    # Only appears for a user who holds one of the booking permissions, and only
    # on an association that installs the app: an unresolvable permission or URL
    # name drops the link.
    AdminSidebarGroup(
        _('Booking'),
        (
            AdminLink(
                _('Bookings'),
                icon='event_available',
                url_name='admin:booking_booking_changelist',
                permission='booking.view_booking',
            ),
            AdminLink(
                _('Rooms'),
                icon='meeting_room',
                url_name='admin:booking_room_changelist',
                permission='booking.view_room',
            ),
            AdminLink(
                _('Closed periods'),
                icon='event_busy',
                url_name='admin:booking_closure_changelist',
                permission='booking.view_closure',
            ),
            AdminLink(
                _('Booking settings'),
                icon='key',
                url_name='admin:booking_bookingsettings_changelist',
                permission='booking.view_bookingsettings',
            ),
        ),
    ),
    # The same rule as the booking group: a link whose permission or URL name
    # does not resolve drops out, so the group is absent on an association that
    # does not install the app.
    AdminSidebarGroup(
        _('Attendance'),
        (
            AdminLink(
                _('Attendance events'),
                icon='how_to_reg',
                url_name='admin:attendance_attendanceevent_changelist',
                permission='attendance.view_attendanceevent',
            ),
            AdminLink(
                _('Attendance changes'),
                icon='history',
                url_name='admin:attendance_attendancechange_changelist',
                permission='attendance.view_attendancechange',
            ),
        ),
    ),
    AdminSidebarGroup(
        _('Members'),
        (
            AdminLink(
                _('Members'), icon='group', url_name='admin:members_member_changelist', permission='members.view_member'
            ),
            AdminLink(
                _('Membership Types'),
                icon='badge',
                url_name='admin:members_membershiptype_changelist',
                permission='members.view_membershiptype',
            ),
            AdminLink(
                _('Subscriptions'),
                icon='card_membership',
                url_name='admin:members_subscription_changelist',
                permission='members.view_subscription',
            ),
            AdminLink(
                _('Subscription Payments'),
                icon='payments',
                url_name='admin:members_subscriptionpayment_changelist',
                permission='members.view_subscriptionpayment',
            ),
            AdminLink(
                _('Functionary Roles'),
                icon='work',
                url_name='admin:functionaries_functionaryrole_changelist',
                any_permissions=('functionaries.view_functionaryrole', 'members.view_functionaryrole'),
            ),
        ),
    ),
    AdminSidebarGroup(
        _('Content'),
        (
            AdminLink(_('News'), icon='article', url_name='admin:news_post_changelist', permission='news.view_post'),
            AdminLink(
                _('News Categories'),
                icon='category',
                url_name='admin:news_category_changelist',
                permission='news.view_category',
            ),
            AdminLink(
                _('Polls'), icon='poll', url_name='admin:polls_question_changelist', permission='polls.view_question'
            ),
            AdminLink(
                _('Static Pages'),
                icon='web',
                url_name='admin:staticpages_staticpage_changelist',
                permission='staticpages.view_staticpage',
            ),
            AdminLink(
                _('Page Navigation'),
                icon='menu_book',
                url_name='admin:staticpages_staticpagenav_changelist',
                permission='staticpages.view_staticpagenav',
            ),
        ),
    ),
    AdminSidebarGroup(
        _('Archive & Publications'),
        (
            AdminLink(
                _('Publication Collections'),
                icon='collections_bookmark',
                url_name='admin:publications_publicationcollection_changelist',
                permission='publications.view_publicationcollection',
            ),
            AdminLink(
                _('Photo Albums'),
                icon='photo_library',
                url_name='admin:gallery_album_changelist',
                any_permissions=('gallery.view_album', 'archive.view_picturecollection'),
            ),
            AdminLink(
                _('Documents'),
                icon='folder',
                url_name='admin:archive_documentcollection_changelist',
                permission='archive.view_documentcollection',
            ),
            AdminLink(
                _('Exams'),
                icon='school',
                url_name='admin:exambank_examarchive_changelist',
                any_permissions=('exambank.view_examarchive', 'archive.view_examcollection'),
            ),
        ),
    ),
    AdminSidebarGroup(
        _('Activities'),
        (
            AdminLink(_('CTF'), icon='military_tech', url_name='admin:ctf_ctf_changelist', permission='ctf.view_ctf'),
            AdminLink(
                _('CTF Post-mortems'),
                icon='flag',
                url_name='admin:ctf_postmortem_changelist',
                any_permissions=('ctf.add_ctf', 'ctf.change_ctf', 'ctf.add_flag', 'ctf.change_flag'),
            ),
            AdminLink(
                _('Lucia'), icon='stars', url_name='admin:lucia_candidate_changelist', permission='lucia.view_candidate'
            ),
        ),
    ),
    AdminSidebarGroup(
        _('Social & Ads'),
        (
            AdminLink(
                _('Samarbetspartners'),
                icon='campaign',
                url_name='admin:ads_adurl_changelist',
                permission='ads.view_adurl',
            ),
            AdminLink(
                _('Instagram URLs'),
                icon='photo_camera',
                url_name='admin:instagram_igurl_changelist',
                any_permissions=('instagram.view_igurl', 'social.view_igurl'),
            ),
            AdminLink(
                _('Harassment Reports'),
                icon='report',
                url_name='admin:harassment_harassment_changelist',
                any_permissions=('harassment.view_harassment', 'social.view_harassment'),
            ),
            AdminLink(
                _('Report Recipients'),
                icon='mail',
                url_name='admin:harassment_harassmentemailrecipient_changelist',
                any_permissions=(
                    'harassment.view_harassmentemailrecipient',
                    'social.view_harassmentemailrecipient',
                ),
            ),
        ),
    ),
    AdminSidebarGroup(
        _('System'),
        (
            AdminLink(
                _('Admin Log'),
                icon='history',
                url_name='admin:admin_logentry_changelist',
                permission='admin.view_logentry',
            ),
            AdminLink(
                _('Permissions'),
                icon='lock',
                url_name='admin:auth_permission_changelist',
                permission='auth.view_permission',
            ),
        ),
    ),
)


def get_sidebar_navigation(request):
    return [group for item in SIDEBAR_NAVIGATION if (group := item.resolve(request)) is not None]
