import random
from typing import cast, Any
from datetime import datetime

from django.db import models
from django.db.models import constraints, Q, F, QuerySet
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from members.models import Member

from django_otp.oath import TOTP
from django_otp.util import random_hex

type Attendee = "Member | NonMemberAttendee"

ATTENDANCE_EVENT_MAX_SLUG_LEN = 50
NON_MEMBER_MAX_NAME_LEN = 255

class AttendanceEvent(models.Model):
    """
    Some kind of event that one can attend.
    """

    title = models.CharField(_("Title"), max_length=255, blank=False)
    description = models.CharField(_("Description"), max_length=255, blank=True)
    start_datetime = models.DateTimeField(_("Start date/time"))
    end_datetime = models.DateTimeField(_("End date/time"), null=True, blank=True)
    allow_non_members = models.BooleanField(_("Allow non-member attendees"), default=True)
    code_secret = models.CharField(_("Code generation secret"), default=random_hex)
    code_validity_time = models.SmallIntegerField(_("Code validity time (seconds)"), default=30)
    slug = models.SlugField(
        _("Slug"),
        unique=True,
        allow_unicode=False,
        max_length=ATTENDANCE_EVENT_MAX_SLUG_LEN,
    )

    def __str__(self):
        return f"{self.title}"

    @property
    def attendance_changes(self) -> QuerySet[AttendanceChange, AttendanceChange]:
        """
        Returns a QuerySet of all AttendanceChanges that apply to this event
        """

        return AttendanceChange.objects.filter(event=self)

    @property
    def has_ended(self) -> bool:
        """
        Has this event ended yet?
        """

        return self.end_datetime is not None and now() > self.end_datetime

    @property
    def totp(self) -> TOTP:
        return TOTP(self.code_secret.encode(), step=self.code_validity_time)

    def present_attendees(self, timestamp: datetime | None = None) -> list[Attendee]:
        """
        Get all attendees who were present at the given timestamp.
        Defaults to the current time.
        """
        timestamp = timestamp or now()
        return [
            x.attendee
            # NOTE: using distinct this way will only work on postgres, which is currently used
            for x in self.attendance_changes.filter(timestamp__lte=timestamp).distinct("user", "non_member").order_by(
                "user_id", "non_member_id", "-timestamp"
            )
            if x.type == AttendanceChange.Type.ENTER
        ]

    def is_attendee_present(self, attendee: Attendee, after_timestamp: datetime | None = None):
        filters: dict[str, Any] = {}
        if after_timestamp:
            filters["timestamp__gte"] = after_timestamp

        if isinstance(attendee, Member):
            filters["user"] = attendee
        else:
            filters["non_member"] = attendee

        try:
            return self.attendance_changes.filter(**filters).latest().type == AttendanceChange.Type.ENTER
        except AttendanceChange.DoesNotExist:
            return False

    def was_attendee_present(self, attendee: Attendee):
        """
        Returns whether or not the given attendee has ever been present during this event
        """

        filters: dict[str, Any] = {}

        if isinstance(attendee, Member):
            filters["user"] = attendee
        else:
            filters["non_member"] = attendee

        try:
            return any(x.type == AttendanceChange.Type.ENTER for x in self.attendance_changes.filter(**filters))
        except AttendanceChange.DoesNotExist:
            return False

    def get_current_code(self) -> int:
        return self.totp.token()

    def time_until_next_code(self) -> float:
        step = self.code_validity_time
        now = self.totp.time
        return step - now % step

    def is_code_valid(self, code: int) -> bool:
        return self.totp.verify(code)


#TODO change to use first_name/last_name fields instead?
class NonMemberAttendee(models.Model):
    """
    An attendee who is not a registered user.
    """

    name = models.CharField(_("Name"), max_length=NON_MEMBER_MAX_NAME_LEN, unique=True)

    # For compatibility with the Member class
    def get_full_name(self):
        return str(self)

    def __str__(self):
        return f"{self.name} ({_('non-member')})"


class AttendanceChange(models.Model):
    """
    A change in the attendance status of someone, either a registered user or a non-member attendee.
    """

    class Type(models.IntegerChoices):
        ENTER = 0, _("Entered")
        LEAVE = 1, _("Left")

    event = models.ForeignKey(AttendanceEvent, on_delete=models.CASCADE, related_name="attendance_changes")
    """The event that this change applies to"""

    # ONE of these fields MUST be non-null, and ONLY ONE field shall be non-null.
    # A change can apply to either a registered member or to a non-member.
    user = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True) # TODO use some other on_delete?
    """The user subject to this change. Can be None, in which case `non_member` will be set"""

    non_member = models.ForeignKey(NonMemberAttendee, on_delete=models.CASCADE, null=True, blank=True)
    """The non-member subject to this change. Can be None, in which case `user` will be set"""

    timestamp = models.DateTimeField(_("Timestamp"), default=now)
    """When this change happened"""

    type = models.IntegerField(_("Type"), choices=Type)
    """What kind of change this is, did the attendee in question enter or leave"""

    class Meta:
        get_latest_by = "timestamp"

        constraints = [
            constraints.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(non_member__isnull=True))
                    | (Q(user__isnull=True) & Q(non_member__isnull=False))
                ),
                name="foreign_keys_ok",
                violation_error_message=_("One and only one of user or non_member must be set")
            )
        ]


    @property
    def attendee(self) -> Attendee:
        """Either a Member or NonMemberAttendee, depending on which field is set"""
        return cast(Attendee, self.user if self.user is not None else self.non_member)

    @property
    def attendee_name(self) -> str:
        """Returns the name of any kind of attendee"""
        if self.user is not None:
            user = cast(Member, self.user)
            return user.full_name
        else:
            non_member = cast(NonMemberAttendee, self.non_member)
            return non_member.name

    def __str__(self):
        # The constraint that usually ensures either user or non_member is set is only checked when saving the model,
        # so this function cannot assume that those fields are correctly set as it is used by e.g the admin page
        user = f"{self.user.username}" if self.user else f"{self.non_member.name} (non-member)" if self.non_member else "<invalid>"
        return f"{user} {self.get_type_display().lower()} {self.event.title} at {self.timestamp}"
