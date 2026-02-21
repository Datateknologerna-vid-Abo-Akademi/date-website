from __future__ import annotations

from django.utils import timezone

from events.models import Event
from members.models import Member, MembershipType, ORDINARY_MEMBER


def seed_smoke_data() -> dict[str, str]:
    # Prefer an existing membership type to avoid sequence-related PK collisions
    # in databases loaded from fixtures with explicit primary keys.
    membership_type = MembershipType.objects.filter(name="CI Smoke").first()
    if membership_type is None:
        membership_type = MembershipType.objects.filter(pk=ORDINARY_MEMBER).first()
    if membership_type is None:
        membership_type, _ = MembershipType.objects.update_or_create(
            pk=9999,
            defaults={"name": "CI Smoke", "permission_profile": ORDINARY_MEMBER},
        )

    user, _ = Member.objects.get_or_create(
        username="ci_smoke",
        defaults={
            "email": "ci-smoke@example.com",
            "first_name": "CI",
            "last_name": "Smoke",
            "membership_type": membership_type,
            "is_active": True,
        },
    )
    user.email = "ci-smoke@example.com"
    user.first_name = "CI"
    user.last_name = "Smoke"
    user.membership_type = membership_type
    user.is_active = True
    user.set_password("ci_smoke_password")
    user.save()

    now = timezone.now()
    event, _ = Event.objects.update_or_create(
        slug="ci-smoke-event",
        defaults={
            "title": "CI Smoke Event",
            "content": "<p>Smoke event for Playwright and API checks.</p>",
            "author": user,
            "published": True,
            "sign_up": True,
            "sign_up_avec": False,
            "members_only": False,
            "passcode": "",
            "captcha": False,
            "sign_up_max_participants": 0,
            "sign_up_members": now - timezone.timedelta(hours=2),
            "sign_up_others": now - timezone.timedelta(hours=2),
            "sign_up_deadline": now + timezone.timedelta(days=2),
            "event_date_start": now + timezone.timedelta(days=5),
            "event_date_end": now + timezone.timedelta(days=5, hours=3),
            "redirect_link": "",
            "parent": None,
        },
    )

    return {
        "username": user.username,
        "event_slug": event.slug,
    }
