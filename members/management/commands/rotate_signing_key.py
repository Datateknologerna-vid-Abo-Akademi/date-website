from django.core.management.base import BaseCommand
from django.db import transaction

from members.key_management import generate_rsa_key


class Command(BaseCommand):
    help = 'Generate a new RSA signing key and retire the current active key.'

    def handle(self, *args, **options):
        from members.models import SigningKey

        pem, kid = generate_rsa_key()

        with transaction.atomic():
            rotated = SigningKey.objects.select_for_update().filter(is_active=True).update(is_active=False)
            SigningKey.objects.create(kid=kid, private_key_pem=pem, is_active=True)

        self.stdout.write(self.style.SUCCESS(
            f'Rotated {rotated} key(s). New key: {kid}\n'
            'Restart all containers to activate the new key.\n'
            'Old keys remain in JWKS until manually deleted from admin.'
        ))
