"""
Celery tasks for JWT Authentication
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import JWTKeyPair, JWTToken, JWTScope

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_tokens():
    """
    Clean up expired JWT tokens from the database.
    This task should be run periodically (e.g., daily) to keep the database clean.
    """
    try:
        # Get current time
        now = timezone.now()
        
        # Find expired tokens that haven't been cleaned up yet
        expired_tokens = JWTToken.objects.filter(
            expires_at__lt=now,
            is_revoked=False  # Only clean up non-revoked tokens to preserve audit trail
        )
        
        expired_count = expired_tokens.count()
        
        if expired_count > 0:
            # Mark expired tokens as revoked instead of deleting them
            # This preserves audit trail while marking them as unusable
            expired_tokens.update(
                is_revoked=True,
                revoked_at=now
            )
            
            logger.info(f"Marked {expired_count} expired JWT tokens as revoked")
        else:
            logger.info("No expired JWT tokens found to clean up")
        
        # Optionally, delete very old revoked tokens (older than 90 days)
        # to prevent database bloat
        old_cutoff = now - timedelta(days=90)
        very_old_tokens = JWTToken.objects.filter(
            revoked_at__lt=old_cutoff,
            is_revoked=True
        )
        
        old_count = very_old_tokens.count()
        if old_count > 0:
            very_old_tokens.delete()
            logger.info(f"Permanently deleted {old_count} very old JWT tokens")
        
        return {
            'success': True,
            'expired_tokens_revoked': expired_count,
            'old_tokens_deleted': old_count,
            'cleanup_time': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during JWT token cleanup: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'cleanup_time': timezone.now().isoformat()
        }


@shared_task
def rotate_jwt_keypairs():
    """
    Rotate JWT key pairs according to security best practices.
    
    This task will:
    1. Check if current key pairs are due for rotation
    2. Generate new key pairs
    3. Gradually phase out old key pairs
    4. Maintain multiple active key pairs for seamless rotation
    """
    try:
        now = timezone.now()
        
        # Get settings for key rotation
        rotation_days = getattr(settings, 'JWT_KEYPAIR_ROTATION_DAYS', 30)
        max_active_keypairs = getattr(settings, 'JWT_MAX_ACTIVE_KEYPAIRS', 3)
        
        # Find key pairs that need rotation
        rotation_cutoff = now - timedelta(days=rotation_days)
        
        # Get current active key pairs
        active_keypairs = JWTKeyPair.objects.filter(is_active=True).order_by('created_at')
        
        needs_rotation = False
        
        # Check if we need to rotate based on age
        if active_keypairs.exists():
            oldest_active = active_keypairs.first()
            if oldest_active.created_at < rotation_cutoff:
                needs_rotation = True
                logger.info(f"Key pair rotation needed - oldest active key pair is {(now - oldest_active.created_at).days} days old")
        else:
            # No active key pairs - definitely need to create one
            needs_rotation = True
            logger.warning("No active JWT key pairs found - creating new key pair")
        
        if needs_rotation:
            with transaction.atomic():
                # Generate new key pair
                new_keypair = JWTKeyPair.generate_keypair()
                logger.info(f"Generated new JWT key pair: {new_keypair.id}")
                
                # If we have too many active key pairs, deactivate the oldest ones
                if active_keypairs.count() >= max_active_keypairs:
                    # Keep the newest (max_active_keypairs - 1) and the new one
                    keypairs_to_deactivate = active_keypairs[:(active_keypairs.count() - max_active_keypairs + 1)]
                    
                    for old_keypair in keypairs_to_deactivate:
                        old_keypair.is_active = False
                        old_keypair.save()
                        logger.info(f"Deactivated old JWT key pair: {old_keypair.id}")
                
                # Update active keypairs count
                current_active_count = JWTKeyPair.objects.filter(is_active=True).count()
                
                return {
                    'success': True,
                    'action': 'rotation_performed',
                    'new_keypair_id': str(new_keypair.id),
                    'active_keypairs_count': current_active_count,
                    'rotation_time': now.isoformat()
                }
        else:
            return {
                'success': True,
                'action': 'rotation_not_needed',
                'active_keypairs_count': active_keypairs.count(),
                'check_time': now.isoformat()
            }
    
    except Exception as e:
        logger.error(f"Error during JWT key pair rotation: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'rotation_time': timezone.now().isoformat()
        }


@shared_task
def cleanup_inactive_keypairs():
    """
    Clean up very old inactive key pairs to prevent database bloat.
    This task removes key pairs that have been inactive for a long time
    and have no associated tokens.
    """
    try:
        now = timezone.now()
        
        # Get settings for cleanup
        cleanup_days = getattr(settings, 'JWT_KEYPAIR_CLEANUP_DAYS', 180)  # 6 months
        
        # Find very old inactive key pairs
        cleanup_cutoff = now - timedelta(days=cleanup_days)
        
        old_inactive_keypairs = JWTKeyPair.objects.filter(
            is_active=False,
            created_at__lt=cleanup_cutoff
        )
        
        cleaned_count = 0
        
        for keypair in old_inactive_keypairs:
            # Check if this keypair has any associated tokens
            if not JWTToken.objects.filter(key_pair=keypair).exists():
                keypair.delete()
                cleaned_count += 1
                logger.info(f"Deleted old unused key pair: {keypair.id}")
            else:
                logger.info(f"Keeping old key pair {keypair.id} - has associated tokens")
        
        return {
            'success': True,
            'keypairs_deleted': cleaned_count,
            'cleanup_time': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during JWT key pair cleanup: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'cleanup_time': timezone.now().isoformat()
        }


@shared_task
def generate_jwt_health_report():
    """
    Generate a health report for the JWT system.
    This task provides insights into token usage, key pair status, etc.
    """
    try:
        now = timezone.now()
        
        # Get statistics
        total_tokens = JWTToken.objects.count()
        active_tokens = JWTToken.objects.filter(
            expires_at__gt=now,
            is_revoked=False
        ).count()
        expired_tokens = JWTToken.objects.filter(
            expires_at__lt=now
        ).count()
        revoked_tokens = JWTToken.objects.filter(is_revoked=True).count()
        
        # Key pair statistics
        active_keypairs = JWTKeyPair.objects.filter(is_active=True).count()
        inactive_keypairs = JWTKeyPair.objects.filter(is_active=False).count()
        
        # Scope statistics
        active_scopes = JWTScope.objects.filter(is_active=True).count()
        
        # Recent activity (last 24 hours)
        yesterday = now - timedelta(hours=24)
        recent_tokens = JWTToken.objects.filter(created_at__gte=yesterday).count()
        
        # Generate report
        report = {
            'timestamp': now.isoformat(),
            'tokens': {
                'total': total_tokens,
                'active': active_tokens,
                'expired': expired_tokens,
                'revoked': revoked_tokens,
                'recent_24h': recent_tokens
            },
            'keypairs': {
                'active': active_keypairs,
                'inactive': inactive_keypairs,
                'total': active_keypairs + inactive_keypairs
            },
            'scopes': {
                'active': active_scopes
            },
            'health_status': 'healthy' if active_keypairs > 0 and active_scopes > 0 else 'warning'
        }
        
        logger.info(f"JWT Health Report: {report}")
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating JWT health report: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def initialize_jwt_scopes():
    """
    Initialize default JWT scopes if they don't exist.
    This task ensures that the basic scopes are always available.
    """
    try:
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
        
        created_scopes = []
        
        for scope_data in default_scopes:
            scope, created = JWTScope.objects.get_or_create(
                name=scope_data['name'],
                defaults={
                    'description': scope_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_scopes.append(scope.name)
                logger.info(f"Created JWT scope: {scope.name}")
        
        return {
            'success': True,
            'created_scopes': created_scopes,
            'total_active_scopes': JWTScope.objects.filter(is_active=True).count(),
            'initialization_time': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error initializing JWT scopes: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'initialization_time': timezone.now().isoformat()
        }
