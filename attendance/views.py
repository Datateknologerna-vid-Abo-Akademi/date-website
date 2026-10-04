from typing import cast

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


class AttendanceEventsView(ListView):
    model = AttendanceEvent
    template_name = "attendance/index.html"

    def get_queryset(self):
        # Soonest first, so the meeting that is running now is at the top and the
        # ones after it follow. Without an order the database decides, which for
        # a list of meetings is not an order a reader can predict.
        return self.model.objects.filter(Q(end_datetime__isnull=True) | Q(end_datetime__gte=now())).order_by(
            "start_datetime"
        )


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
        if self.request.method == "GET" and "code" in self.request.GET:
            ctx["prefilled_code"] = self.request.GET.get("code")

        if self.request.user.is_authenticated:
            user = cast(Member, self.request.user)
            ctx["is_present"] = self.object.is_attendee_present(user)

        return ctx

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
        return HttpResponseSeeOther(self._safe_next(request) or self.request.path)


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
        # parse one either, so the value the code carries has to be absolute.
        ctx["event_url"] = self.request.build_absolute_uri(reverse("attendance-event-view", args=[self.object.slug]))
        # Entries rather than labels: the list identifies a row by the attendee's
        # key so two people with the same name stay two rows, and the name is the
        # label the websocket broadcast carries.
        ctx["present_attendees"] = [attendee_entry(attendee) for attendee in self.object.present_attendees()]

        return ctx

    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())
