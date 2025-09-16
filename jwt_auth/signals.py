"""
Django signals for JWT authentication
"""
import logging
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def create_default_jwt_scopes(sender, **kwargs):
    """
    Create default JWT scopes after migrations are applied.
    This ensures that the basic scopes are always available.
    """
    # Only run for our app
    if sender.name != 'jwt_auth':
        return
    
    try:
        # Import here to avoid circular imports
        from .models import JWTScope
        
        default_scopes = [
            {
                'name': 'base',
                'description': 'Basic access to authenticated endpoints'
            },
            {
                'name': 'image_upload',
                'description': 'Permission to upload images and media files'
            },
            {
                'name': 'event_management',
                'description': 'Permission to create and manage events'
            },
            {
                'name': 'admin',
                'description': 'Full administrative access'
            }
        ]
        
        created_count = 0
        for scope_data in default_scopes:
            scope, created = JWTScope.objects.get_or_create(
                name=scope_data['name'],
                defaults={
                    'description': scope_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                logger.info(f"Created default JWT scope: {scope.name}")
        
        if created_count > 0:
            logger.info(f"Created {created_count} default JWT scopes")
        else:
            logger.debug("All default JWT scopes already exist")
            
    except Exception as e:
        logger.error(f"Error creating default JWT scopes: {str(e)}")


@receiver(post_migrate)
def ensure_jwt_keypair_exists(sender, **kwargs):
    """
    Ensure that at least one JWT keypair exists after migrations.
    This is critical for the JWT system to function.
    """
    # Only run for our app
    if sender.name != 'jwt_auth':
        return
    
    try:
        # Import here to avoid circular imports
        from .models import JWTKeyPair
        
        # Check if any active keypair exists
        if not JWTKeyPair.objects.filter(is_active=True).exists():
            # Create initial keypair
            keypair = JWTKeyPair.generate_keypair()
            logger.info(f"Created initial JWT keypair: {keypair.id}")
        else:
            logger.debug("Active JWT keypairs already exist")
            
    except Exception as e:
        logger.error(f"Error ensuring JWT keypair exists: {str(e)}")
