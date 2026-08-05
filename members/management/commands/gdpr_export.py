import json

from django.core.management.base import BaseCommand

from members.gdpr import collect_personal_data


class Command(BaseCommand):
    help = "Export all personal data held for an email address (GDPR access request)."

    def add_arguments(self, parser):
        parser.add_argument('email', help="Email address to look up.")
        parser.add_argument(
            '--output',
            '-o',
            dest='output',
            default=None,
            help="Write the JSON export to this file instead of stdout.",
        )

    def handle(self, *args, **options):
        email = options['email']
        data = collect_personal_data(email)
        payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        if options['output']:
            with open(options['output'], 'w', encoding='utf-8') as fh:
                fh.write(payload)
            self.stdout.write(self.style.SUCCESS(f"Wrote export to {options['output']}"))
        else:
            self.stdout.write(payload)
