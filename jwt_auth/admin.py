from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import JWTKeyPair, JWTToken


@admin.register(JWTKeyPair)
class JWTKeyPairAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'expires_at', 'public_key_preview']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'public_key_preview', 'private_key_preview']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'expires_at')
        }),
        ('Key Information', {
            'fields': ('public_key_preview', 'private_key_preview', 'created_at'),
            'classes': ('collapse',)
        }),
        ('Raw Keys', {
            'fields': ('public_key_pem', 'private_key_pem'),
            'classes': ('collapse',),
            'description': 'Raw PEM formatted keys. Handle with care!'
        })
    )
    
    def public_key_preview(self, obj):
        if obj.public_key_pem:
            lines = obj.public_key_pem.split('\n')
            preview = '\n'.join(lines[:5]) + '\n...' if len(lines) > 5 else obj.public_key_pem
            return format_html('<pre style="font-size: 10px;">{}</pre>', preview)
        return 'No public key'
    public_key_preview.short_description = 'Public Key Preview'
    
    def private_key_preview(self, obj):
        if obj.private_key_pem:
            lines = obj.private_key_pem.split('\n')
            preview = '\n'.join(lines[:5]) + '\n...' if len(lines) > 5 else obj.private_key_pem
            return format_html('<pre style="font-size: 10px; color: red;">{}</pre>', preview)
        return 'No private key'
    private_key_preview.short_description = 'Private Key Preview (Sensitive!)'
    
    actions = ['generate_new_key_pair', 'deactivate_key_pairs']
    
    def generate_new_key_pair(self, request, queryset):
        """Admin action to generate a new key pair"""
        try:
            # Deactivate existing key pairs
            JWTKeyPair.objects.filter(is_active=True).update(is_active=False)
            
            # Generate new key pair
            import uuid
            key_name = f"keypair_{uuid.uuid4().hex[:8]}"
            new_key_pair = JWTKeyPair.generate_key_pair(key_name)
            
            self.message_user(request, f"Successfully generated new key pair: {new_key_pair.name}")
        except Exception as e:
            self.message_user(request, f"Error generating key pair: {str(e)}", level='ERROR')
    
    generate_new_key_pair.short_description = "Generate new key pair (deactivates existing)"
    
    def deactivate_key_pairs(self, request, queryset):
        """Admin action to deactivate selected key pairs"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} key pair(s)")
    
    deactivate_key_pairs.short_description = "Deactivate selected key pairs"


@admin.register(JWTToken)
class JWTTokenAdmin(admin.ModelAdmin):
    list_display = ['token_id', 'user', 'purpose', 'issued_at', 'expires_at', 'is_revoked', 'key_pair']
    list_filter = ['is_revoked', 'purpose', 'issued_at', 'key_pair']
    search_fields = ['user__username', 'user__email', 'token_id', 'purpose']
    readonly_fields = ['token_id', 'user', 'key_pair', 'issued_at', 'expires_at']
    
    fieldsets = (
        ('Token Information', {
            'fields': ('token_id', 'user', 'key_pair', 'purpose')
        }),
        ('Timestamps', {
            'fields': ('issued_at', 'expires_at')
        }),
        ('Status', {
            'fields': ('is_revoked',)
        })
    )
    
    actions = ['revoke_tokens', 'unrevoke_tokens']
    
    def revoke_tokens(self, request, queryset):
        """Admin action to revoke selected tokens"""
        updated = queryset.update(is_revoked=True)
        self.message_user(request, f"Revoked {updated} token(s)")
    
    revoke_tokens.short_description = "Revoke selected tokens"
    
    def unrevoke_tokens(self, request, queryset):
        """Admin action to unrevoke selected tokens"""
        updated = queryset.update(is_revoked=False)
        self.message_user(request, f"Unrevoked {updated} token(s)")
    
    unrevoke_tokens.short_description = "Unrevoke selected tokens"
    
    def has_add_permission(self, request):
        """Prevent manual token creation through admin"""
        return False
