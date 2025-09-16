"""
Django management command for JWT authentication setup and maintenance
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jwt_auth.models import JWTKeyPair, JWTScope, JWTToken
from jwt_auth.tasks import (
    cleanup_expired_tokens,
    rotate_jwt_keypairs,
    cleanup_inactive_keypairs,
    generate_jwt_health_report,
    initialize_jwt_scopes
)


class Command(BaseCommand):
    help = 'JWT Authentication management commands'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=[
                'init', 'cleanup', 'rotate', 'health', 'status',
                'create-keypair', 'create-scopes', 'cleanup-keypairs'
            ],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force the action even if not normally needed'
        )

    def handle(self, *args, **options):
        action = options['action']
        force = options['force']
        
        self.stdout.write(f"Executing JWT auth action: {action}")
        
        if action == 'init':
            self.handle_init()
        elif action == 'cleanup':
            self.handle_cleanup()
        elif action == 'rotate':
            self.handle_rotate(force)
        elif action == 'health':
            self.handle_health()
        elif action == 'status':
            self.handle_status()
        elif action == 'create-keypair':
            self.handle_create_keypair()
        elif action == 'create-scopes':
            self.handle_create_scopes()
        elif action == 'cleanup-keypairs':
            self.handle_cleanup_keypairs()

    def handle_init(self):
        """Initialize JWT authentication system"""
        self.stdout.write("Initializing JWT authentication system...")
        
        # Create default scopes
        scope_result = initialize_jwt_scopes.delay()
        self.stdout.write(f"Scope initialization result: {scope_result.get()}")
        
        # Create initial keypair if none exists
        if not JWTKeyPair.objects.filter(is_active=True).exists():
            keypair = JWTKeyPair.generate_keypair()
            self.stdout.write(
                self.style.SUCCESS(f"Created initial JWT keypair: {keypair.id}")
            )
        else:
            self.stdout.write("Active JWT keypairs already exist")
        
        self.stdout.write(self.style.SUCCESS("JWT authentication system initialized"))

    def handle_cleanup(self):
        """Run cleanup tasks"""
        self.stdout.write("Running JWT token cleanup...")
        
        result = cleanup_expired_tokens.delay()
        cleanup_result = result.get()
        
        if cleanup_result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleanup completed: {cleanup_result['expired_tokens_revoked']} "
                    f"tokens revoked, {cleanup_result['old_tokens_deleted']} old tokens deleted"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Cleanup failed: {cleanup_result['error']}")
            )

    def handle_rotate(self, force=False):
        """Rotate JWT keypairs"""
        self.stdout.write("Checking JWT keypair rotation...")
        
        if force:
            # Force rotation by temporarily setting all keypairs as old
            from datetime import timedelta
            from django.conf import settings
            
            rotation_days = getattr(settings, 'JWT_KEYPAIR_ROTATION_DAYS', 30)
            old_date = timezone.now() - timedelta(days=rotation_days + 1)
            
            # Temporarily mark all as old for forced rotation
            JWTKeyPair.objects.filter(is_active=True).update(created_at=old_date)
            self.stdout.write("Forcing keypair rotation...")
        
        result = rotate_jwt_keypairs.delay()
        rotation_result = result.get()
        
        if rotation_result['success']:
            if rotation_result['action'] == 'rotation_performed':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Keypair rotation completed: new keypair {rotation_result['new_keypair_id']}, "
                        f"{rotation_result['active_keypairs_count']} active keypairs"
                    )
                )
            else:
                self.stdout.write("Keypair rotation not needed at this time")
        else:
            self.stdout.write(
                self.style.ERROR(f"Keypair rotation failed: {rotation_result['error']}")
            )

    def handle_health(self):
        """Generate health report"""
        self.stdout.write("Generating JWT health report...")
        
        result = generate_jwt_health_report.delay()
        health_result = result.get()
        
        if 'error' not in health_result:
            self.stdout.write("=== JWT Health Report ===")
            self.stdout.write(f"Timestamp: {health_result['timestamp']}")
            self.stdout.write(f"Health Status: {health_result['health_status']}")
            
            tokens = health_result['tokens']
            self.stdout.write(f"\nTokens:")
            self.stdout.write(f"  Total: {tokens['total']}")
            self.stdout.write(f"  Active: {tokens['active']}")
            self.stdout.write(f"  Expired: {tokens['expired']}")
            self.stdout.write(f"  Revoked: {tokens['revoked']}")
            self.stdout.write(f"  Recent (24h): {tokens['recent_24h']}")
            
            keypairs = health_result['keypairs']
            self.stdout.write(f"\nKeypairs:")
            self.stdout.write(f"  Active: {keypairs['active']}")
            self.stdout.write(f"  Inactive: {keypairs['inactive']}")
            self.stdout.write(f"  Total: {keypairs['total']}")
            
            scopes = health_result['scopes']
            self.stdout.write(f"\nScopes:")
            self.stdout.write(f"  Active: {scopes['active']}")
            
            status_style = self.style.SUCCESS if health_result['health_status'] == 'healthy' else self.style.WARNING
            self.stdout.write(status_style(f"\nOverall Status: {health_result['health_status']}"))
        else:
            self.stdout.write(
                self.style.ERROR(f"Health report failed: {health_result['error']}")
            )

    def handle_status(self):
        """Show current JWT system status"""
        self.stdout.write("=== JWT Authentication Status ===")
        
        # Keypairs
        active_keypairs = JWTKeyPair.objects.filter(is_active=True)
        inactive_keypairs = JWTKeyPair.objects.filter(is_active=False)
        
        self.stdout.write(f"Active Keypairs: {active_keypairs.count()}")
        for kp in active_keypairs:
            age_days = (timezone.now() - kp.created_at).days
            self.stdout.write(f"  - {kp.id} (created {age_days} days ago)")
        
        self.stdout.write(f"Inactive Keypairs: {inactive_keypairs.count()}")
        
        # Scopes
        active_scopes = JWTScope.objects.filter(is_active=True)
        self.stdout.write(f"Active Scopes: {active_scopes.count()}")
        for scope in active_scopes:
            self.stdout.write(f"  - {scope.name}: {scope.description}")
        
        # Tokens
        now = timezone.now()
        total_tokens = JWTToken.objects.count()
        active_tokens = JWTToken.objects.filter(expires_at__gt=now, is_revoked=False).count()
        
        self.stdout.write(f"Total Tokens: {total_tokens}")
        self.stdout.write(f"Active Tokens: {active_tokens}")

    def handle_create_keypair(self):
        """Create a new keypair"""
        self.stdout.write("Creating new JWT keypair...")
        
        keypair = JWTKeyPair.generate_keypair()
        self.stdout.write(
            self.style.SUCCESS(f"Created new JWT keypair: {keypair.id}")
        )

    def handle_create_scopes(self):
        """Create default scopes"""
        self.stdout.write("Creating default JWT scopes...")
        
        result = initialize_jwt_scopes.delay()
        scope_result = result.get()
        
        if scope_result['success']:
            created_scopes = scope_result['created_scopes']
            if created_scopes:
                self.stdout.write(
                    self.style.SUCCESS(f"Created scopes: {', '.join(created_scopes)}")
                )
            else:
                self.stdout.write("All default scopes already exist")
            
            self.stdout.write(f"Total active scopes: {scope_result['total_active_scopes']}")
        else:
            self.stdout.write(
                self.style.ERROR(f"Scope creation failed: {scope_result['error']}")
            )

    def handle_cleanup_keypairs(self):
        """Clean up old inactive keypairs"""
        self.stdout.write("Cleaning up old inactive keypairs...")
        
        result = cleanup_inactive_keypairs.delay()
        cleanup_result = result.get()
        
        if cleanup_result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleanup completed: {cleanup_result['keypairs_deleted']} old keypairs deleted"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Keypair cleanup failed: {cleanup_result['error']}")
            )
