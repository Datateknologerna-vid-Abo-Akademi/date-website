import random
from typing import cast, Any
from datetime import datetime

from django.db import models
from django.db.models import constraints, Q, F
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _


from members.models import Member

type Attendee = Member | "NonMemberAttendee"

ATTENDANCE_EVENT_MAX_SLUG_LEN = 50
NON_MEMBER_MAX_NAME_LEN = 255

# The secret could of course be anything,
# but a random 5-digit number seemed like a reasonable default
def generate_event_secret():
    return str(random.randint(10000, 99999))


class AttendanceEvent(models.Model):
    """
    Some kind of event that one can attend.
    """

    title = models.CharField(_("Title"), max_length=255, blank=False)
    description = models.CharField(_("Description"), max_length=255, blank=True)
    start_datetime = models.DateTimeField(_("Start date/time"))
    end_datetime = models.DateTimeField(_("End date/time"), null=True, blank=True)
    secret = models.CharField(_("Secret"), default=generate_event_secret)
    allow_non_members = models.BooleanField(_("Allow non-member attendees"), default=True)
    slug = models.SlugField(
        _("Slug"),
        unique=True,
        allow_unicode=False,
        max_length=ATTENDANCE_EVENT_MAX_SLUG_LEN,
    )

    def __str__(self):
        return f"{self.title}"

    @property
    def attendance_changes(self):
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

    def present_attendees(self, timestamp: datetime | None = None) -> list[Member | NonMemberAttendee]:
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


#TODO change to use first_name/last_name fields instead?
class NonMemberAttendee(models.Model):
    """
    An attendee who is not a registered user.
    """

    name = models.CharField(_("Name"), max_length=NON_MEMBER_MAX_NAME_LEN, unique=True)

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
    def attendee(self) -> Member | NonMemberAttendee:
        """Either a Member or NonMemberAttendee, depending on which field is set"""
        return cast(Member | NonMemberAttendee, self.user if self.user is not None else self.non_member)

    def __str__(self):
        # The constraint that usually ensures either user or non_member is set is only checked when saving the model,
        # so this function cannot assume that those fields are correctly set as it is used by e.g the admin page
        user = f"{self.user.username}" if self.user else f"{self.non_member.name} (non-member)" if self.non_member else "<invalid>"
        return f"{user} {self.get_type_display().lower()} {self.event.title} at {self.timestamp}"
