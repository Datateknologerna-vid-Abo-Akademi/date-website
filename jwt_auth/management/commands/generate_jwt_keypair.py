from django.core.management.base import BaseCommand
from jwt_auth.models import JWTKeyPair
import uuid


class Command(BaseCommand):
    help = 'Generate a new JWT key pair'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            help='Name for the key pair (default: auto-generated)',
        )
        parser.add_argument(
            '--key-size',
            type=int,
            default=2048,
            help='RSA key size in bits (default: 2048)',
        )
        parser.add_argument(
            '--deactivate-existing',
            action='store_true',
            help='Deactivate existing active key pairs',
        )

    def handle(self, *args, **options):
        name = options['name']
        key_size = options['key_size']
        deactivate_existing = options['deactivate_existing']

        if not name:
            name = f"keypair_{uuid.uuid4().hex[:8]}"

        try:
            # Deactivate existing key pairs if requested
            if deactivate_existing:
                updated = JWTKeyPair.objects.filter(is_active=True).update(is_active=False)
                if updated > 0:
                    self.stdout.write(
                        self.style.WARNING(f"Deactivated {updated} existing key pair(s)")
                    )

            # Generate new key pair
            key_pair = JWTKeyPair.generate_key_pair(name, key_size)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully generated JWT key pair: {key_pair.name}\n"
                    f"Key size: {key_size} bits\n"
                    f"Status: {'Active' if key_pair.is_active else 'Inactive'}"
                )
            )
            
            # Display public key for verification
            self.stdout.write("\nPublic key (PEM format):")
            self.stdout.write(key_pair.public_key_pem)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error generating key pair: {str(e)}")
            )
