from django.core.management.base import BaseCommand

from members.gdpr import anonymize_personal_data


class Command(BaseCommand):
    help = (
        "Anonymize or delete all personal data held for an email address "
        "(GDPR erasure request). Use --dry-run to preview what would change."
    )

    def add_arguments(self, parser):
        parser.add_argument('email', help="Email address to erase.")
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Show what would change without modifying anything.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        summary = anonymize_personal_data(options['email'], dry_run=dry_run)

        verb = "Would anonymize" if dry_run else "Anonymized"
        self.stdout.write(self.style.MIGRATE_HEADING(f"{verb} data for {summary['email']}"))
        for label, key in (
            ("members", 'members'),
            ("event attendee rows", 'attendees'),
            ("harassment reports (email)", 'harassment_anonymized'),
        ):
            self.stdout.write(f"  {label}: {summary[key]}")
        for label, key in (
            ("CTF guesses deleted", 'guesses_deleted'),
            ("2FA devices deleted", 'devices_deleted'),
            ("alumni tokens deleted", 'tokens_deleted'),
        ):
            self.stdout.write(f"  {label}: {summary[key]}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write("Dry run only, no changes were made. Re-run without --dry-run to apply.")
