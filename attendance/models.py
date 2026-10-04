from datetime import datetime
from typing import Any, cast

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, constraints
from django.utils.formats import date_format, time_format
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop, pgettext_lazy
from django_otp.oath import TOTP
from django_otp.util import random_hex

from members.models import Member

type Attendee = "Member | NonMemberAttendee"

ATTENDANCE_EVENT_MAX_SLUG_LEN = 50
NON_MEMBER_MAX_NAME_LEN = 255


def attendee_label(attendee: Attendee) -> str:
    """The name to show for an attendee, in a form that does not depend on the language.

    The websocket broadcast and the staff overview page it feeds both use this, so
    a name arriving over the socket matches the one already rendered. The event
    page keeps the translated guest marker in its change log, which is rendered in
    one language and never has to match a socket payload.

    `NonMemberAttendee.__str__` appends a translated "(icke-medlem)". The payload
    is built in the participant's request language while the staff page renders in
    the staff member's, so a translated marker cannot be part of a label that has
    to match across that boundary.
    """
    if isinstance(attendee, Member):
        return attendee.get_full_name()

    return cast(NonMemberAttendee, attendee).name


def attendee_key(attendee: Attendee) -> str:
    """A stable identity for an attendee, unlike the name.

    Two members can share a name, and a guest may type a name that a member
    already has. The overview list has to keep those apart, so it identifies a
    row by the row's primary key and its kind, not by the label it displays.

    The two kinds are namespaced because a member and a guest are different
    tables: their primary keys are not comparable.
    """
    if isinstance(attendee, Member):
        return f"user-{attendee.pk}"

    return f"non-member-{cast(NonMemberAttendee, attendee).pk}"


def attendee_entry(attendee: Attendee) -> dict[str, str]:
    """One entry of the staff overview list: what to show and what to match on.

    The page, the connect snapshot and the change broadcast all build their
    entries through this, so an attendee has the same key in every one of them.
    """
    return {"key": attendee_key(attendee), "name": attendee_label(attendee)}


class AttendanceEvent(models.Model):
    """
    Some kind of event that one can attend.
    """

    title = models.CharField(_("Titel"), max_length=255, blank=False)
    description = models.CharField(_("Beskrivning"), max_length=255, blank=True)
    start_datetime = models.DateTimeField(_("Starttid"))
    end_datetime = models.DateTimeField(_("Sluttid"), null=True, blank=True)
    allow_non_members = models.BooleanField(_("Tillåt icke-medlemmar att delta"), default=False)
    code_secret = models.CharField(_("Kodens genereringsnyckel"), default=random_hex)
    # At least one second: django_otp divides by the step, so a zero or negative
    # period breaks the code calculation outright.
    code_validity_time = models.SmallIntegerField(
        _("Kodens giltighetsperiod (sekunder)"), default=30, validators=[MinValueValidator(1)]
    )
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
            for x in self.attendance_changes.filter(timestamp__lte=timestamp)
            # Otherwise every attendee costs a query of its own for the name.
            .select_related("user", "non_member")
            .distinct("user", "non_member")
            .order_by("user_id", "non_member_id", "-timestamp")
            if x.type == AttendanceChange.Type.ENTER
        ]

    def present_count(self, timestamp: datetime | None = None) -> int:
        """
        Get how many attendees were present at the given timestamp.
        Defaults to the current time.

        The same answer as ``len(present_attendees(timestamp))``, in a form that
        also runs on SQLite. ``present_attendees`` asks the database for one row
        per attendee with ``distinct("user", "non_member")``, which compiles to
        PostgreSQL's ``DISTINCT ON`` and raises ``NotSupportedError`` on any other
        backend (NOTE on that method), so a caller that only wants the number
        cannot use it. Here the changes are read newest first and the first row
        per attendee is kept in Python instead, which costs one query and no
        per-attendee query, and the arrivals among those rows are counted.
        """
        timestamp = timestamp or now()
        seen: set[tuple[str, int | None]] = set()
        count = 0

        for change in self.attendance_changes.filter(timestamp__lte=timestamp).order_by("-timestamp"):
            # A member and a guest are different attendees, so the kind has to be
            # part of the identity: their primary keys are not comparable, which
            # is the same reason attendee_key namespaces it. The check constraint
            # says exactly one of the two fields is set.
            key = ("user", change.user_id) if change.user_id is not None else ("non_member", change.non_member_id)
            if key in seen:
                continue

            seen.add(key)
            if change.type == AttendanceChange.Type.ENTER:
                count += 1

        return count

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

        return any(x.type == AttendanceChange.Type.ENTER for x in self.attendance_changes.filter(**filters))

    def get_current_code(self) -> int:
        return self.totp.token()

    def time_until_next_code(self) -> float:
        step = self.code_validity_time
        now = self.totp.time
        return step - now % step

    def is_code_valid(self, code: int) -> bool:
        """The code for the current period, or for the one before it."""
        totp = self.totp
        if totp.verify(code):
            return True

        # One period of grace: the code that was on screen when somebody started
        # typing still works after it rotates. Without it a participant who is a
        # little slow gets "Fel kod", and five of those now start a lockout.
        # `verify` looks only at the current step, so the previous period is
        # reached by asking the same secret to count one step back; the period
        # after this one is deliberately not accepted.
        previous = TOTP(totp.key, step=totp.step, t0=totp.t0, digits=totp.digits, drift=-1)
        return previous.verify(code)


class AttendancePoll(models.Model):
    """
    A poll that only the people in a meeting's room may vote on.

    The link lives here and not on ``polls.Question``: every association installs
    ``polls``, while ``attendance`` is installed by DaTe alone
    (``core/settings/date.py``), and a field on the question pointing at this app
    would fail ``manage.py check`` on the other six. ``polls`` reaches this model
    through ``Question.attendance_poll``.

    One poll belongs to at most one meeting, which is what the one-to-one says.
    A poll without a row here is an ordinary poll and keeps the vote rules it
    always had.
    """

    # The poll that requires presence.
    question = models.OneToOneField(
        "polls.Question",
        on_delete=models.CASCADE,
        related_name="attendance_poll",
        verbose_name=_("Fråga"),
    )

    # The meeting whose room the voter has to be in.
    event = models.ForeignKey(
        AttendanceEvent,
        on_delete=models.CASCADE,
        related_name="polls",
        verbose_name=_("Närvaroevenemang"),
    )

    class Meta:
        verbose_name = _("närvarokrav")
        verbose_name_plural = _("närvarokrav")

    def __str__(self):
        return f"{self.event}: {self.question}"


class NonMemberAttendee(models.Model):
    """
    An attendee who is not a registered user.

    The name is the identity: a guest has no account to key on, and the check-in
    view calls get_or_create(name=...), so two people with the same name share
    one row across every event. Splitting it into first and last name would not
    change that, it would take an address or a per-event record to tell them
    apart, which is more than this list needs.
    """

    name = models.CharField(_("Namn"), max_length=NON_MEMBER_MAX_NAME_LEN, unique=True)

    class Meta:
        verbose_name = _("deltagare, icke-medlem")
        verbose_name_plural = _("deltagare, icke-medlemmar")

    def __str__(self):
        return f"{self.name} ({_('icke-medlem')})"

    # For compatibility with the Member class
    def get_full_name(self):
        return str(self)


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

    event = models.ForeignKey(
        AttendanceEvent,
        on_delete=models.CASCADE,
        related_name="attendance_changes",
        verbose_name=_("Närvaroevenemang"),
    )
    """The event that this change applies to"""

    # ONE of these fields MUST be non-null, and ONLY ONE field shall be non-null.
    # A change can apply to either a registered member or to a non-member.
    # Deleting a member takes their own attendance changes with them. That is
    # what the other member-linked records in this project do (polls.Vote.user,
    # members.SubscriptionPayment.member) and what an erasure request needs. The
    # minutes, not this table, are the record that outlives a member.
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=user_verbose_name,
    )
    """The user subject to this change. Can be None, in which case `non_member` will be set"""

    non_member = models.ForeignKey(
        NonMemberAttendee,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=non_member_verbose_name,
    )
    """The non-member subject to this change. Can be None, in which case `user` will be set"""

    timestamp = models.DateTimeField(_("Tidpunkt"), default=now)
    """When this change happened"""

    type = models.IntegerField(_("Typ"), choices=Type)
    """What kind of change this is, did the attendee in question enter or leave"""

    class Meta:
        verbose_name = _("närvaroändring")
        verbose_name_plural = _("närvaroändringar")
        get_latest_by = "timestamp"
        # Newest first: the change log is read to see who just arrived or left.
        ordering = ["-timestamp"]

        constraints = [
            constraints.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(non_member__isnull=True))
                    | (Q(user__isnull=True) & Q(non_member__isnull=False))
                ),
                name="foreign_keys_ok",
                violation_error_message=_("Exakt en av '%(user)s' eller '%(non_member)s' måste anges.")
                % {"user": user_verbose_name, "non_member": non_member_verbose_name},
            )
        ]

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

    @property
    def attendee(self) -> Attendee:
        """Either a Member or NonMemberAttendee, depending on which field is set"""
        return cast(Attendee, self.user if self.user is not None else self.non_member)

    @property
    def attendee_name(self) -> str:
        """Returns the language-independent name of any kind of attendee"""
        return attendee_label(self.attendee)

    @property
    def attendee_key(self) -> str:
        """Returns the stable identity of this change's attendee, not their name"""
        return attendee_key(self.attendee)
