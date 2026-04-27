from typing import cast

from django.shortcuts import render
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpRequest
from django.views.generic import View, ListView
from django.views.generic.detail import SingleObjectMixin
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.db.models import Q


from members.models import Member
from . import forms, websocket
from .models import AttendanceChange, AttendanceEvent, NonMemberAttendee, Attendee


class AttendanceEventsView(ListView):
    model = AttendanceEvent
    template_name = "attendance/index.html"

    def get_queryset(self):
        return self.model.objects.filter(Q(end_datetime__isnull=True) | Q(end_datetime__gte=now()))


class AttendanceEventDetailView(UserPassesTestMixin, SingleObjectMixin[AttendanceEvent], View):
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

        if self.request.user.is_authenticated:
            user = cast(Member, self.request.user)
            ctx["is_present"] = self.object.is_attendee_present(user)

        return ctx

    def _bad_request(self, request, **kwargs):
        return render(request, self.template_name, self.get_ctx(**kwargs), status=403)

    def _conflict(self, request, **kwargs):
        return render(request, self.template_name, self.get_ctx(**kwargs), status=409)


    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())


    def post(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()


        form = forms.AttendanceChangeForm(request.POST)
        if not form.is_valid():
            error_dict = { f"{field}_error": errors[0] for field, errors in form.errors.items()}
            return self._bad_request(request, **error_dict)

        if not self.object.is_code_valid(form.cleaned_data["code"]):
            return self._bad_request(request, code_error="Invalid code")

        non_member_name: str = form.cleaned_data["non_member_name"]
        type: AttendanceChange.Type = form.cleaned_data["type"]

        if request.user.is_anonymous and len(non_member_name) == 0:
            return self._bad_request(request, non_member_name_error="Name must be specified if you are not logged in")


        # This could theoretically end up in a situation where another request gets through and
        # causes nonsensical attendance change records (e.g going from ENTER -> LEAVE, but the request is sent twice so two LEAVE records are created),
        # but it wouldn't really matter in the end so this doesn't have to be atomic

        attendee: Attendee
        if request.user.is_authenticated:
            attendee_type, attendee = "user", cast(Attendee, request.user)
        else:
            non_member, created = NonMemberAttendee.objects.get_or_create(name=non_member_name)
            attendee_type, attendee = "non_member", non_member

        match type:
            case AttendanceChange.Type.ENTER:
                if self.object.is_attendee_present(attendee):
                    return self._conflict(request, generic_error="Cannot enter an event where you are already present")

            case AttendanceChange.Type.LEAVE:
                if not self.object.is_attendee_present(attendee):
                    return self._conflict(request, generic_error="Cannot leave an event where you are not present")

            case unhandled:
                raise Exception(f"unhandled AttendanceChange.Type {unhandled}")

        change = AttendanceChange(event=self.object, type=type, **{attendee_type: attendee})
        change.save()
        websocket.send_attendance_change(self.object.slug, change)

        return render(request, self.template_name, self.get_ctx())

class AttendanceEventOverview(UserPassesTestMixin, SingleObjectMixin[AttendanceEvent], View):
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

        return ctx

    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())
