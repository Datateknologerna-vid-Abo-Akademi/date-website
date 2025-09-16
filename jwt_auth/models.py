import os
import json
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
import jwt

User = get_user_model()


# JWT Token Scopes
class JWTScope(models.Model):
    """Model to define available JWT token scopes"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Scope name (e.g., 'base', 'image_upload')")
    description = models.TextField(help_text="Description of what this scope allows")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "JWT Scope"
        verbose_name_plural = "JWT Scopes"
        ordering = ['name']
    
    def __str__(self):
        return self.name

    @classmethod
    def get_default_scopes(cls):
        """Get default scopes for authenticated users"""
        return cls.objects.filter(name='base', is_active=True)
    
    @classmethod
    def initialize_default_scopes(cls):
        """Initialize default scopes if they don't exist"""
        default_scopes = [
            {
                'name': 'base',
                'description': 'Basic API access - allows reading user profile and basic data'
            },
            {
                'name': 'image_upload',
                'description': 'Image upload permissions - allows uploading images to archive'
            },
            {
                'name': 'event_management',
                'description': 'Event management - allows creating and managing events'
            },
            {
                'name': 'admin',
                'description': 'Administrative access - full API access (staff only)'
            }
        ]
        
        for scope_data in default_scopes:
            cls.objects.get_or_create(
                name=scope_data['name'],
                defaults={'description': scope_data['description']}
            )


class JWTKeyPair(models.Model):
    """Model to store RSA key pairs for JWT signing and verification"""
    
    name = models.CharField(max_length=100, unique=True, help_text="Unique identifier for this key pair")
    private_key_pem = models.TextField(help_text="PEM encoded private key")
    public_key_pem = models.TextField(help_text="PEM encoded public key")
    is_active = models.BooleanField(default=True, help_text="Whether this key pair is active for signing")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date for key rotation")
    
    class Meta:
        verbose_name = "JWT Key Pair"
        verbose_name_plural = "JWT Key Pairs"
        ordering = ['-created_at']

    def __str__(self):
        return f"Key Pair: {self.name}"

    @property
    def private_key(self):
        """Get the private key object from PEM string"""
        return serialization.load_pem_private_key(
            self.private_key_pem.encode('utf-8'),
            password=None
        )

    @property
    def public_key(self):
        """Get the public key object from PEM string"""
        return serialization.load_pem_public_key(
            self.public_key_pem.encode('utf-8')
        )

    @classmethod
    def generate_key_pair(cls, name, key_size=2048):
        """Generate a new RSA key pair and save it to the database"""
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize keys to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Create and save the key pair
        key_pair = cls.objects.create(
            name=name,
            private_key_pem=private_pem,
            public_key_pem=public_pem
        )
        
        return key_pair

    @classmethod
    def get_active_key_pair(cls):
        """Get the currently active key pair for signing"""
        return cls.objects.filter(is_active=True).first()

    def generate_jwt_token(self, user, scopes=None, additional_claims=None, expires_in_hours=24):
        """Generate a JWT token for the given user with specified scopes"""
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_in_hours)
        
        # Get scope names
        scope_names = []
        if scopes:
            scope_names = [scope.name for scope in scopes]
        else:
            # Default to base scope
            default_scopes = JWTScope.get_default_scopes()
            scope_names = [scope.name for scope in default_scopes]
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'scopes': scope_names,
            'iat': now,
            'exp': expires_at,
            'iss': getattr(settings, 'JWT_ISSUER', 'date-website'),
            'aud': getattr(settings, 'JWT_AUDIENCE', 'date-website-api'),
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        # Generate the token
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm='RS256',
            headers={'kid': self.name}  # Key ID for key rotation
        )
        
        return token

    def verify_jwt_token(self, token):
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=['RS256'],
                audience=getattr(settings, 'JWT_AUDIENCE', 'date-website-api'),
                issuer=getattr(settings, 'JWT_ISSUER', 'date-website')
            )
            return payload
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")


class JWTToken(models.Model):
    """Model to track issued JWT tokens (optional, for logging/audit purposes)"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jwt_tokens')
    key_pair = models.ForeignKey(JWTKeyPair, on_delete=models.CASCADE)
    scopes = models.ManyToManyField(JWTScope, blank=True)
    token_id = models.CharField(max_length=100, unique=True)  # jti claim
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
    purpose = models.CharField(max_length=100, blank=True, help_text="Purpose/description of the token")
    
    class Meta:
        verbose_name = "JWT Token"
        verbose_name_plural = "JWT Tokens"
        ordering = ['-issued_at']

    def __str__(self):
        return f"JWT Token for {self.user.username} - {self.token_id}"

    def revoke(self):
        """Revoke this token"""
        self.is_revoked = True
        self.save()
    
    @property
    def scope_names(self):
        """Get list of scope names for this token"""
        return list(self.scopes.values_list('name', flat=True))
