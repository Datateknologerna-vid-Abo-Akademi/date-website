from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import JWTKeyPair, JWTToken, JWTScope

User = get_user_model()


class JWTScopeSerializer(serializers.ModelSerializer):
    """Serializer for JWT scopes"""
    
    class Meta:
        model = JWTScope
        fields = ['name', 'description', 'is_active']
        read_only_fields = ['is_active']


class TokenGenerateRequestSerializer(serializers.Serializer):
    """Serializer for JWT token generation requests"""
    
    purpose = serializers.CharField(
        max_length=100, 
        required=False, 
        default='api_access',
        help_text="Purpose or description of the token"
    )
    expires_in_hours = serializers.IntegerField(
        min_value=1, 
        max_value=168,  # 7 days max
        default=24,
        help_text="Token expiration time in hours (1-168)"
    )
    scopes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of scope names to grant (defaults to 'base')"
    )
    save_token_record = serializers.BooleanField(
        default=True,
        help_text="Whether to save token record for audit purposes"
    )

    def validate_scopes(self, value):
        """Validate that requested scopes exist and user has permission"""
        if not value:
            return ['base']  # Default scope
        
        # Check if scopes exist
        existing_scopes = JWTScope.objects.filter(
            name__in=value, 
            is_active=True
        ).values_list('name', flat=True)
        
        invalid_scopes = set(value) - set(existing_scopes)
        if invalid_scopes:
            raise serializers.ValidationError(
                f"Invalid scopes: {', '.join(invalid_scopes)}"
            )
        
        # Check user permissions for admin scope
        request = self.context.get('request')
        if request and 'admin' in value:
            if not (request.user.is_staff or request.user.is_superuser):
                raise serializers.ValidationError(
                    "Admin scope requires staff privileges"
                )
        
        return value


class TokenGenerateResponseSerializer(serializers.Serializer):
    """Serializer for JWT token generation responses"""
    
    token = serializers.CharField(help_text="Generated JWT token")
    token_type = serializers.CharField(default="Bearer")
    expires_in_hours = serializers.IntegerField()
    issued_at = serializers.DateTimeField()
    scopes = serializers.ListField(child=serializers.CharField())
    purpose = serializers.CharField()
    key_id = serializers.CharField()


class TokenVerifyRequestSerializer(serializers.Serializer):
    """Serializer for JWT token verification requests"""
    
    token = serializers.CharField(help_text="JWT token to verify")


class TokenVerifyResponseSerializer(serializers.Serializer):
    """Serializer for JWT token verification responses"""
    
    valid = serializers.BooleanField()
    payload = serializers.DictField(required=False)
    error = serializers.CharField(required=False)
    key_id = serializers.CharField(required=False)


class TokenRevokeRequestSerializer(serializers.Serializer):
    """Serializer for JWT token revocation requests"""
    
    token_id = serializers.CharField(help_text="Token ID (jti claim) to revoke")


class TokenRevokeResponseSerializer(serializers.Serializer):
    """Serializer for JWT token revocation responses"""
    
    revoked = serializers.BooleanField()
    token_id = serializers.CharField()


class JWTTokenSerializer(serializers.ModelSerializer):
    """Serializer for JWT token records"""
    
    scopes = JWTScopeSerializer(many=True, read_only=True)
    scope_names = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    key_pair_name = serializers.CharField(source='key_pair.name', read_only=True)
    
    class Meta:
        model = JWTToken
        fields = [
            'token_id', 'purpose', 'issued_at', 'expires_at', 
            'is_revoked', 'scopes', 'scope_names', 'key_pair_name'
        ]
        read_only_fields = [
            'token_id', 'issued_at', 'expires_at', 'key_pair_name'
        ]


class PublicKeySerializer(serializers.Serializer):
    """Serializer for public key information"""
    
    kid = serializers.CharField(help_text="Key ID")
    kty = serializers.CharField(default="RSA")
    use = serializers.CharField(default="sig")
    alg = serializers.CharField(default="RS256")
    pem = serializers.CharField(help_text="PEM formatted public key")
    created_at = serializers.DateTimeField()


class PublicKeysResponseSerializer(serializers.Serializer):
    """Serializer for public keys response"""
    
    keys = PublicKeySerializer(many=True)
    count = serializers.IntegerField()
