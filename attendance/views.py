from django.shortcuts import render
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpRequest
from django.views.generic import View, ListView
from django.views.generic.detail import SingleObjectMixin
from django.utils.translation import gettext_lazy as _


from . import forms
from .models import AttendanceChange, AttendanceEvent, NonMemberAttendee, Attendee


class AttendanceEventsView(ListView):
    model = AttendanceEvent
    template_name = "attendance/index.html"


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
        ctx["user"] = self.request.user
        ctx["present_attendees"] = self.object.present_attendees()

        if self.request.user.is_authenticated:
            ctx["is_present"] = self.object.is_attendee_present(self.request.user)

        return ctx

    def _bad_request(self, request, error_message):
        return render(request, self.template_name, self.get_ctx(error_message=error_message), status=403)

    def _conflict(self, request, error_message):
        return render(request, self.template_name, self.get_ctx(error_message=error_message), status=409)


    def get(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()

        return render(request, self.template_name, self.get_ctx())


    def post(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()


        form = forms.AttendanceChangeForm(request.POST)
        if not form.is_valid():
            return self._bad_request(request, f"invalid form: {form.errors}")

        if form.cleaned_data["secret"] != self.object.secret:
            return self._bad_request(request, "invalid secret")

        non_member_name: str = form.cleaned_data["non_member_name"]
        type: AttendanceChange.Type = form.cleaned_data["type"]

        if request.user.is_anonymous and len(non_member_name) == 0:
            return self._bad_request(request, "must specify name if not logged in")


        # This could theoretically end up in a situation where another request gets through and
        # causes nonsensical attendance change records (e.g going from ENTER -> LEAVE, but the request is sent twice so two LEAVE records are created),
        # but it wouldn't really matter in the end so this doesn't have to be atomic

        attendee: Attendee
        if request.user.is_authenticated:
            attendee_type, attendee = "user", request.user
        else:
            non_member, created = NonMemberAttendee.objects.get_or_create(name=non_member_name)
            attendee_type, attendee = "non_member", non_member

        match type:
            case AttendanceChange.Type.ENTER:
                if self.object.is_attendee_present(attendee):
                    return self._conflict(request, "cannot enter an event where you are already present")

            case AttendanceChange.Type.LEAVE:
                if not self.object.is_attendee_present(attendee):
                    return self._conflict(request, "cannot leave an event where you are not present")

            case unhandled:
                raise Exception(f"unhandled AttendanceChange.Type {unhandled}")

        change = AttendanceChange(event=self.object, type=type, **{attendee_type: attendee})
        change.save()

        return render(request, self.template_name, self.get_ctx())
