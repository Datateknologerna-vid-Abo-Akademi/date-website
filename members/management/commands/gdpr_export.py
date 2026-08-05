import json
import os
import stat

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
            self._write_file(options['output'], payload)
            self.stdout.write(self.style.SUCCESS(f"Wrote export to {options['output']}"))
        else:
            self.stderr.write(
                self.style.WARNING(
                    "Warning: the export contains personal data and may include sensitive "
                    "content such as harassment reports. Prefer --output with a protected file."
                )
            )
            self.stdout.write(payload)

    def _write_file(self, path, payload):
        """Write the export with owner-only permissions (0600)."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(payload)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
