from datetime import timedelta
from typing import cast
from urllib.parse import quote, unquote

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Model, Q
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View
from django.views.generic.detail import SingleObjectMixin

from members.models import Member

from . import forms, limits, websocket
from .models import AttendanceChange, AttendanceEvent, Attendee, NonMemberAttendee, attendee_entry


class HttpResponseSeeOther(HttpResponseRedirect):
    status_code = 303


# A meeting that recorded no end stays on the public list while it started less
# than this many hours ago. A meeting is yesterday's news the next day, and
# without a bound a meeting whose end nobody filled in would sit on the public
# page for ever. Only the list forgets it: its own page, its code and its QR code
# keep working for anyone who has the link.
NO_END_LISTING_HOURS = 24

# The name a guest typed, kept in a cookie so their next visit is one tap. The
# cookie is convenience only: the log's identity is the typed name, not the
# cookie, so a different name is a different attendee and clearing cookies costs
# nothing but retyping. The value is percent-encoded, because a Set-Cookie header
# is latin-1 and `http.cookies` escapes a name like "Gäst" into a form a browser
# hands back verbatim and Django then cannot parse, so the name would be lost.
NON_MEMBER_NAME_COOKIE = "attendance_non_member_name"
NON_MEMBER_NAME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


class AttendanceEventsView(ListView):
    model = AttendanceEvent
    template_name = "attendance/index.html"

    def get_queryset(self):
        # A meeting with an end leaves the list once that moment has passed. One
        # without an end is listed while it started less than NO_END_LISTING_HOURS
        # ago, so a forgotten end does not pin a meeting to the top of the public
        # list for ever.
        #
        # Soonest first, so the meeting that is running now is at the top and the
        # ones after it follow. Without an order the database decides, which for
        # a list of meetings is not an order a reader can predict.
        moment = now()
        return self.model.objects.filter(
            Q(end_datetime__gte=moment)
            | Q(end_datetime__isnull=True, start_datetime__gt=moment - timedelta(hours=NO_END_LISTING_HOURS))
        ).order_by("start_datetime")


class AttendanceEventObjectMixin[ModelT: Model](SingleObjectMixin[ModelT]):
    """Fetches the event once per request.

    ``UserPassesTestMixin.test_func`` runs before the handler and has to look the
    object up to decide, so without this every detail and overview request would
    fetch the same row twice.
    """

    def get_object(self, queryset=None):
        if not hasattr(self, "object"):
            self.object = super().get_object(queryset)

        return self.object


class AttendanceEventDetailView(UserPassesTestMixin, AttendanceEventObjectMixin[AttendanceEvent], View):
    model = AttendanceEvent
    template_name = "attendance/detail.html"

    def test_func(self):
        """Only allows authenticated users if the AttendanceEvent does not allow non-members"""
        self.object = self.get_object()

        if not self.object.allow_non_members:
            return self.request.user.is_authenticated
        return True

    def get_ctx(self, **kwargs):
        ctx = {**kwargs}

        ctx["object"] = self.object
        ctx["can_see_overview"] = AttendanceEventOverview.is_user_allowed(self.request.user)
        ctx["user"] = self.request.user
        ctx["present_attendees"] = self.object.present_attendees()
        # select_related so the staff change log costs one query rather than one
        # per row for the names. Lazy, so it is free for everyone else.
        ctx["changes"] = self.object.attendance_changes.select_related("user", "non_member")
        ctx["next"] = self._safe_next(self.request)
        ctx["prefilled_name"] = ""
        # None means the page cannot say either way, and then it draws no state at
        # all: an anonymous visitor with no remembered name is not an attendee
        # here. A member and a remembered guest both get an answer.
        ctx["is_present"] = None
        if self.request.method == "GET" and "code" in self.request.GET:
            ctx["prefilled_code"] = self.request.GET.get("code")

        if self.request.user.is_authenticated:
            user = cast(Member, self.request.user)
            ctx["is_present"] = self.object.is_attendee_present(user)
        elif self.request.method == "GET":
            remembered = self._remembered_name(self.request)
            ctx["prefilled_name"] = remembered
            if remembered:
                # Never create on a GET: the cookie is a claim about a name, not a
                # guest. It only lets the page say whether that name's row is
                # currently in the room.
                guest = NonMemberAttendee.objects.filter(name=remembered).first()
                if guest is not None:
                    ctx["is_present"] = self.object.is_attendee_present(guest)

        return ctx

    def _remembered_name(self, request: HttpRequest) -> str:
        """The guest name the visitor typed on an earlier visit, or an empty string.

        Convenience only. It is what the name box is prefilled with, and it is
        never written into a change: the guest still has to press the button and
        the log is keyed on the submitted name. The value is decoded here, which
        is the other half of the percent-encoding the response writes.
        """
        return unquote(request.COOKIES.get(NON_MEMBER_NAME_COOKIE, ""))

    def _safe_next(self, request: HttpRequest) -> str:
        """The local page to return to after a check-in, or an empty string.

        ``next`` arrives from the query string on GET and from the form on POST,
        and the value is checked before it is used or rendered: without the check
        the parameter would be an open redirect, and reflecting a hostile one into
        the hidden input would hand the same URL to whoever reads the markup.

        A refused attempt (a wrong code, a lockout, a conflict) renders the page
        again through ``get_ctx``, so the value survives in the form and the
        participant still lands on the page that sent them here.
        """
        candidate = request.POST.get("next", "") if request.method == "POST" else request.GET.get("next", "")
        if candidate and url_has_allowed_host_and_scheme(
            candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return candidate

        return ""

    def _bad_request(self, request, **kwargs):
        return render(request, self.template_name, self.get_ctx(**kwargs), status=403)

    def _conflict(self, request, **kwargs):
        return render(request, self.template_name, self.get_ctx(**kwargs), status=409)

    def _locked_out(self, request, seconds: int):
        message = _("För många felaktiga koder. Försök igen om %(seconds)s sekunder.") % {"seconds": seconds}

        return render(request, self.template_name, self.get_ctx(lockout_error=message), status=429)

    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())

    def post(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        form = forms.AttendanceChangeForm(request.POST)
        if not form.is_valid():
            error_dict = {f"{field}_error": errors[0] for field, errors in form.errors.items()}
            # A malformed change type has no field of its own on the page. Mapping
            # it onto the message the template does render keeps a stale or
            # tampered form from failing silently.
            if "type_error" in error_dict:
                error_dict["generic_error"] = error_dict.pop("type_error")
            return self._bad_request(request, **error_dict)

        # A malformed submission is not a code attempt, so it costs nothing.
        lockout = limits.lockout_remaining(request)
        if lockout:
            return self._locked_out(request, lockout)

        if not self.object.is_code_valid(form.cleaned_data["code"]):
            limits.register_failure(request)
            lockout = limits.lockout_remaining(request)
            if lockout:
                return self._locked_out(request, lockout)
            return self._bad_request(request, code_error=_("Fel kod"))

        limits.clear(request)

        non_member_name: str = form.cleaned_data["non_member_name"]
        type: AttendanceChange.Type = form.cleaned_data["type"]

        if request.user.is_anonymous and len(non_member_name) == 0:
            return self._bad_request(request, non_member_name_error=_("Namn måste anges om du inte är inloggad"))

        # This could theoretically end up in a situation where another request gets through and causes
        # nonsensical attendance change records (e.g going from ENTER -> LEAVE, but the request is sent
        # twice so two LEAVE records are created), but it wouldn't really matter in the end, so this
        # does not have to be atomic

        attendee: Attendee
        if request.user.is_authenticated:
            attendee_type, attendee = "user", cast(Attendee, request.user)
        else:
            non_member, created = NonMemberAttendee.objects.get_or_create(name=non_member_name)
            attendee_type, attendee = "non_member", non_member

        match type:
            case AttendanceChange.Type.ENTER:
                if self.object.is_attendee_present(attendee):
                    return self._conflict(
                        request,
                        generic_error=_("Du kan inte gå in i ett evenemang var du redan är närvarande"),
                    )

            case AttendanceChange.Type.LEAVE:
                if not self.object.is_attendee_present(attendee):
                    return self._conflict(
                        request,
                        generic_error=_("Du kan inte gå ut ur ett evenemang var du inte är närvarande"),
                    )

            case unhandled:
                raise Exception(f"unhandled AttendanceChange.Type {unhandled}")

        change = AttendanceChange(event=self.object, type=type, **{attendee_type: attendee})
        change.save()
        websocket.send_attendance_change(self.object.slug, change)

        # Back to the page that asked for this check-in when it named one, and to
        # this page without the "code" query parameter otherwise.
        response = HttpResponseSeeOther(self._safe_next(request) or self.request.path)

        # A successful guest change remembers the typed name so checking out and
        # back in is one tap. The cookie is convenience only: the log's identity is
        # the name, so a different name is a different attendee and clearing
        # cookies costs nothing but retyping. A member's request writes nothing,
        # because a member is identified by the account and not by a name box.
        # Percent-encoded, so the value is ASCII whatever the guest typed and a
        # Set-Cookie header can always carry it (see NON_MEMBER_NAME_COOKIE).
        if attendee_type == "non_member":
            response.set_cookie(
                NON_MEMBER_NAME_COOKIE,
                quote(non_member_name, safe=""),
                max_age=NON_MEMBER_NAME_COOKIE_MAX_AGE,
                path="/",
                secure=request.is_secure(),
                httponly=True,
                samesite="Lax",
            )

        return response


class AttendanceEventOverview(UserPassesTestMixin, AttendanceEventObjectMixin[AttendanceEvent], View):
    model = AttendanceEvent
    template_name = "attendance/overview.html"

    @staticmethod
    def is_user_allowed(user) -> bool:
        return user.is_authenticated and user.is_staff

    def test_func(self) -> bool:
        """Only allows staff to access the code view page"""
        self.object = self.get_object()

        return self.is_user_allowed(self.request.user)

    def get_ctx(self, **kwargs):
        ctx = {**kwargs}

        ctx["object"] = self.object
        ctx["code"] = self.object.get_current_code()
        # The event page as an absolute URL, for the QR code. A bare path is not a
        # link to a phone's camera app, and the check-in page's own scanner cannot
        # parse one either, so the value has to be absolute, and it is the address
        # this page is being served from: the deployment trusts the ingress's
        # forwarded host and protocol (`USE_X_FORWARDED_HOST` and
        # `TRUST_X_FORWARDED_PROTO`, both on by default in the chart), so that is
        # the association's own domain in production, and the address of this
        # instance everywhere else rather than a settings value shared by all of
        # them. `booking/emails.py` uses the `SITE_URL` content variable instead,
        # because mail is composed where there is no request to ask.
        ctx["event_url"] = self.request.build_absolute_uri(reverse("attendance-event-view", args=[self.object.slug]))
        # Entries rather than labels: the list identifies a row by the attendee's
        # key so two people with the same name stay two rows, and the name is the
        # label the websocket broadcast carries.
        ctx["present_attendees"] = [attendee_entry(attendee) for attendee in self.object.present_attendees()]

        return ctx

    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())
