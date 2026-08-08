"""Shared helpers for GDPR access and erasure commands.

Both management commands (``gdpr_export`` and ``gdpr_delete``) resolve a
person by email address and walk the models that can hold personal data.
The delete command anonymizes rather than deletes database rows in places
where other records (public content, invoices, poll results) depend on them.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet


def _model(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _device_model(app_label):
    """Return the 2FA device model for an otp plugin app label."""
    model_name = 'TOTPDevice' if app_label == 'otp_totp' else 'StaticDevice'
    return _model(app_label, model_name)


def _empty_queryset() -> QuerySet:
    """Return an empty queryset for the user model (all apps are optional)."""
    return get_user_model().objects.none()


def find_members_by_email(email: str) -> QuerySet:
    """Return members whose email matches, case-insensitively."""
    Member = get_user_model()
    return Member.objects.filter(email__iexact=email.strip())


def find_attendees_by_email(email: str) -> QuerySet:
    EventAttendees = _model('events', 'EventAttendees')
    if EventAttendees is None:
        return _empty_queryset()
    return EventAttendees.objects.filter(email__iexact=email.strip())


def find_harassment_by_email(email: str) -> QuerySet:
    Harassment = _model('harassment', 'Harassment')
    if Harassment is None:
        return _empty_queryset()
    return Harassment.objects.filter(email__iexact=email.strip())


def find_alumni_tokens_by_email(email: str) -> QuerySet:
    AlumniUpdateToken = _model('alumni', 'AlumniUpdateToken')
    if AlumniUpdateToken is None:
        return _empty_queryset()
    return AlumniUpdateToken.objects.filter(email__iexact=email.strip())


def _member_summary(member) -> dict:
    return {
        'username': member.username,
        'email': member.email,
        'first_name': member.first_name,
        'last_name': member.last_name,
        'phone': member.phone,
        'address': member.address,
        'zip_code': member.zip_code,
        'city': member.city,
        'country': member.country,
        'year_of_admission': member.year_of_admission,
        'github_id': member.github_id,
        'membership_type': str(member.membership_type),
        'is_active': member.is_active,
        'is_superuser': member.is_superuser,
        'last_login': member.last_login.isoformat() if member.last_login else None,
        'groups': [str(group) for group in member.groups.all()],
    }


def collect_personal_data(email: str) -> dict[str, Any]:
    """Collect all personal data held for an email address, as a dict."""
    data: dict[str, Any] = {
        'query_email': email.strip(),
        'members': [],
        'subscription_payments': [],
        'event_attendees': [],
        'authored_events': [],
        'authored_news': [],
        'functionary_roles': [],
        'ctf_flags_solved': [],
        'ctf_guesses': [],
        'poll_votes': [],
        'billing_invoices': [],
        'alumni_tokens': [],
        'alumni_recipient_lists': [],
        'harassment_reports': [],
        'harassment_recipient_lists': [],
    }

    for member in find_members_by_email(email):
        data['members'].append(_member_summary(member))

        SubscriptionPayment = _model('members', 'SubscriptionPayment')
        if SubscriptionPayment is not None:
            for payment in SubscriptionPayment.objects.filter(member=member):
                data['subscription_payments'].append(
                    {
                        'subscription': str(payment.subscription),
                        'date_paid': payment.date_paid.isoformat(),
                        'date_expires': payment.date_expires.isoformat() if payment.date_expires else None,
                        'amount_paid': str(payment.amount_paid) if payment.amount_paid is not None else None,
                    }
                )

        Event = _model('events', 'Event')
        if Event is not None:
            for event in Event.objects.filter(author=member):
                data['authored_events'].append({'title': event.title, 'slug': event.slug, 'id': event.id})

        Post = _model('news', 'Post')
        if Post is not None:
            for post in Post.objects.filter(author=member):
                data['authored_news'].append({'title': post.title, 'slug': post.slug, 'id': post.id})

        Functionary = _model('functionaries', 'Functionary')
        if Functionary is not None:
            for functionary in Functionary.objects.filter(member=member):
                data['functionary_roles'].append(
                    {
                        'role': str(functionary.functionary_role),
                        'name': functionary.name,
                        'year': functionary.year,
                    }
                )

        Flag = _model('ctf', 'Flag')
        if Flag is not None:
            for flag in Flag.objects.filter(solver=member):
                data['ctf_flags_solved'].append(
                    {
                        'flag': flag.title,
                        'ctf': str(flag.ctf),
                        'solved_date': flag.solved_date.isoformat() if flag.solved_date else None,
                    }
                )

        Guess = _model('ctf', 'Guess')
        if Guess is not None:
            for guess in Guess.objects.filter(user=member):
                data['ctf_guesses'].append(
                    {
                        'ctf': str(guess.ctf),
                        'flag': guess.flag.title,
                        'guess': guess.guess,
                        'correct': guess.correct,
                        'timestamp': guess.timestamp.isoformat(),
                    }
                )

        Vote = _model('polls', 'Vote')
        if Vote is not None:
            for vote in Vote.objects.filter(user=member):
                data['poll_votes'].append(
                    {
                        'question': str(vote.question),
                        'voted_at': vote.voted_at.isoformat(),
                    }
                )

    for attendee in find_attendees_by_email(email):
        data['event_attendees'].append(
            {
                'event': str(attendee.event),
                'name': attendee.user,
                'email': attendee.email,
                'anonymous': attendee.anonymous,
                'preferences': attendee.preferences,
                'time_registered': attendee.time_registered.isoformat(),
                'avec_for': str(attendee.avec_for) if attendee.avec_for_id else None,
            }
        )
        EventInvoice = _model('billing', 'EventInvoice')
        if EventInvoice is not None:
            for invoice in EventInvoice.objects.filter(participant=attendee):
                data['billing_invoices'].append(
                    {
                        'event': str(attendee.event),
                        'invoice_number': invoice.invoice_number,
                        'reference_number': invoice.reference_number,
                        'amount': invoice.amount,
                        'currency': invoice.currency,
                        'invoice_date': invoice.invoice_date.isoformat(),
                        'due_date': invoice.due_date.isoformat(),
                    }
                )

    for token in find_alumni_tokens_by_email(email):
        data['alumni_tokens'].append({'created_at': token.created_at.isoformat()})

    AlumniEmailRecipient = _model('alumni', 'AlumniEmailRecipient')
    if AlumniEmailRecipient is not None:
        for recipient in AlumniEmailRecipient.objects.filter(recipient_email__iexact=email):
            data['alumni_recipient_lists'].append({'email': recipient.recipient_email})

    for report in find_harassment_by_email(email):
        data['harassment_reports'].append({'email': report.email, 'message': report.message})

    HarassmentEmailRecipient = _model('harassment', 'HarassmentEmailRecipient')
    if HarassmentEmailRecipient is not None:
        for recipient in HarassmentEmailRecipient.objects.filter(recipient_email__iexact=email):
            data['harassment_recipient_lists'].append({'email': recipient.recipient_email})

    return data


def anonymize_personal_data(email: str, dry_run: bool = True) -> dict:
    """Anonymize or delete personal data for an email address.

    Policy:
    - Member row is kept but anonymized (public content, votes and
      subscription records reference it).
    - Event attendee rows are kept but anonymized, since billing invoices
      cascade from them and are accounting records.
    - CTF guesses, 2FA devices and alumni tokens are deleted.
    - Harassment report emails are anonymized, messages are kept.
    - Poll votes, authored content, functionary history and invoices are kept.
    """
    email = email.strip()
    summary: dict[str, Any] = {
        'email': email,
        'dry_run': dry_run,
        'members': 0,
        'attendees': 0,
        'guesses_deleted': 0,
        'devices_deleted': 0,
        'tokens_deleted': 0,
        'alumni_recipients_removed': 0,
        'harassment_anonymized': 0,
        'harassment_recipients_removed': 0,
        'functionaries_anonymized': 0,
    }

    with transaction.atomic():
        for member in find_members_by_email(email):
            summary['members'] += 1

            for device_model in ('otp_totp', 'otp_static'):
                Device = _device_model(device_model)
                if Device is not None:
                    summary['devices_deleted'] += Device.objects.filter(user=member).count()

            Guess = _model('ctf', 'Guess')
            if Guess is not None:
                summary['guesses_deleted'] += Guess.objects.filter(user=member).count()

            if not dry_run:
                member.username = _anonymized_username(member)
                member.email = None
                member.first_name = ''
                member.last_name = ''
                member.phone = ''
                member.address = ''
                member.zip_code = ''
                member.city = ''
                member.country = ''
                member.year_of_admission = None
                member.github_id = None
                member.is_active = False
                member.is_superuser = False
                member.set_unusable_password()
                member.groups.clear()
                member.user_permissions.clear()
                member.save()

                for device_model in ('otp_totp', 'otp_static'):
                    Device = _device_model(device_model)
                    if Device is not None:
                        Device.objects.filter(user=member).delete()

                Guess = _model('ctf', 'Guess')
                if Guess is not None:
                    Guess.objects.filter(user=member).delete()

            Functionary = _model('functionaries', 'Functionary')
            if Functionary is not None:
                summary['functionaries_anonymized'] += Functionary.objects.filter(member=member).count()
                if not dry_run:
                    Functionary.objects.filter(member=member).update(name='Anonym')

        for attendee in find_attendees_by_email(email):
            summary['attendees'] += 1
            if not dry_run:
                attendee.user = 'Anonym'
                attendee.email = None
                attendee.preferences = {}
                attendee.anonymous = True
                attendee.save()

        for token in find_alumni_tokens_by_email(email):
            summary['tokens_deleted'] += 1
            if not dry_run:
                token.delete()

        AlumniEmailRecipient = _model('alumni', 'AlumniEmailRecipient')
        if AlumniEmailRecipient is not None:
            summary['alumni_recipients_removed'] = AlumniEmailRecipient.objects.filter(
                recipient_email__iexact=email
            ).count()
            if not dry_run:
                AlumniEmailRecipient.objects.filter(recipient_email__iexact=email).delete()

        for report in find_harassment_by_email(email):
            summary['harassment_anonymized'] += 1
            if not dry_run:
                report.email = None
                report.save()

        HarassmentEmailRecipient = _model('harassment', 'HarassmentEmailRecipient')
        if HarassmentEmailRecipient is not None:
            summary['harassment_recipients_removed'] = HarassmentEmailRecipient.objects.filter(
                recipient_email__iexact=email
            ).count()
            if not dry_run:
                HarassmentEmailRecipient.objects.filter(recipient_email__iexact=email).delete()

    return summary


def _anonymized_username(member) -> str:
    """Return a unique anonymized username that fits the 20-char limit."""
    base = f"anonymized_{member.pk}"
    if len(base) <= 20:
        candidate = base
    else:
        candidate = f"anon_{member.pk}"[:20]
    if not type(member).objects.filter(username=candidate).exclude(pk=member.pk).exists():
        return candidate
    suffix = hex(member.pk)[2:][-4:]
    return f"anon_{suffix}"[:20]
