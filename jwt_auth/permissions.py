"""
Custom permissions for JWT Authentication API
"""
from rest_framework import permissions
from .models import JWTScope


class JWTScopePermission(permissions.BasePermission):
    """
    Custom permission to check if user has the required JWT scopes
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get required scopes from view
        required_scopes = getattr(view, 'required_scopes', [])
        
        # If no scopes required, allow access
        if not required_scopes:
            return True
        
        # Check if user has all required scopes
        user_scopes = JWTScope.objects.filter(
            is_active=True
        ).values_list('name', flat=True)
        
        # For now, we'll allow access if the user is authenticated
        # In the future, you might want to implement user-specific scope checking
        return True


class HasJWTScope(permissions.BasePermission):
    """
    Permission class to check specific JWT scopes
    """
    
    def __init__(self, *scopes):
        self.required_scopes = scopes
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if all required scopes are available
        available_scopes = JWTScope.objects.filter(
            is_active=True,
            name__in=self.required_scopes
        ).count()
        
        return available_scopes == len(self.required_scopes)
