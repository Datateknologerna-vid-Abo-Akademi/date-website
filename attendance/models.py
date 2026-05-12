import random
from typing import cast, Any
from datetime import datetime

from django.db import models
from django.db.models import constraints, Q, QuerySet
from django.utils.timezone import now, localtime
from django.utils.translation import gettext_lazy as _, pgettext_lazy, gettext_noop
from django.utils.formats import date_format, time_format

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

    title = models.CharField(_("Titel"), max_length=255, blank=False)
    description = models.CharField(_("Beskrivning"), max_length=255, blank=True)
    start_datetime = models.DateTimeField(_("Starttid"))
    end_datetime = models.DateTimeField(_("Sluttid"), null=True, blank=True)
    allow_non_members = models.BooleanField(_("Tillåt icke-medlemmar att delta"), default=True)
    code_secret = models.CharField(_("Kodens genereringnyckel"), default=random_hex)
    code_validity_time = models.SmallIntegerField(_("Kodens giltighetsperiod (sekunder)"), default=30)
    slug = models.SlugField(
        _("Slug"),
        unique=True,
        allow_unicode=False,
        max_length=ATTENDANCE_EVENT_MAX_SLUG_LEN,
    )

    class Meta:
        verbose_name = pgettext_lazy("singular", "närvaroevenemang")
        verbose_name_plural = pgettext_lazy("plural", "närvaroevenemang")

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


# TODO change to use first_name/last_name fields instead?
class NonMemberAttendee(models.Model):
    """
    An attendee who is not a registered user.
    """

    name = models.CharField(_("Namn"), max_length=NON_MEMBER_MAX_NAME_LEN, unique=True)

    class Meta:
        verbose_name = _("deltagare, icke-medlem")
        verbose_name_plural = _("deltagare, icke-medlemmar")

    # For compatibility with the Member class
    def get_full_name(self):
        return str(self)

    def __str__(self):
        return f"{self.name} ({_('icke-medlem')})"


user_verbose_name = _("Användare")
non_member_verbose_name = _("Icke-medlem")
class AttendanceChange(models.Model):
    """
    A change in the attendance status of someone, either a registered user or a non-member attendee.
    """

    # These have to be contextually translated depending on where they are used
    class Type(models.IntegerChoices):
        ENTER = 0, gettext_noop("Anlände")
        LEAVE = 1, gettext_noop("Lämnade")

    # This is here to trick makemessages into generating the contextual translation strings
    class _TranslationDummy:
        _ = pgettext_lazy("left/entered some event", "Anlände")
        _ = pgettext_lazy("left/entered some event", "Lämnade")
        _ = pgettext_lazy("left/entered in general", "Anlände")
        _ = pgettext_lazy("left/entered in general", "Lämnade")

    event = models.ForeignKey(AttendanceEvent, on_delete=models.CASCADE, related_name="attendance_changes", verbose_name=_("Närvaroevenemang"))
    """The event that this change applies to"""

    # ONE of these fields MUST be non-null, and ONLY ONE field shall be non-null.
    # A change can apply to either a registered member or to a non-member.
    user = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True, verbose_name=user_verbose_name) # TODO use some other on_delete?
    """The user subject to this change. Can be None, in which case `non_member` will be set"""

    non_member = models.ForeignKey(NonMemberAttendee, on_delete=models.CASCADE, null=True, blank=True, verbose_name=non_member_verbose_name)
    """The non-member subject to this change. Can be None, in which case `user` will be set"""

    timestamp = models.DateTimeField(_("Tidpunkt"), default=now)
    """When this change happened"""

    type = models.IntegerField(_("Typ"), choices=Type)
    """What kind of change this is, did the attendee in question enter or leave"""

    class Meta:
        verbose_name = _("närvaroändring")
        verbose_name_plural = _("närvaroändingar")
        get_latest_by = "timestamp"

        constraints = [
            constraints.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(non_member__isnull=True))
                    | (Q(user__isnull=True) & Q(non_member__isnull=False))
                ),
                name="foreign_keys_ok",
                violation_error_message=_(
                    "Exakt en av '%(user)s' eller '%(non_member)s' måste anges."
                )
                % {"user": user_verbose_name, "non_member": non_member_verbose_name},
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
        if (self.user and self.non_member) or (not self.user and not self.non_member):
            user = _("<ogiltig>")
        else:
            user = (self.user or self.non_member).get_full_name()

        timestamp = localtime(self.timestamp)
        return _("%(user)s %(action)s %(event)s den %(date)s kl %(time)s") % {
            "user": user,
            "action": pgettext_lazy("left/entered some event", self.get_type_display()).lower(),
            "event": self.event.title,
            "date": date_format(timestamp),
            "time": time_format(timestamp),
        }
