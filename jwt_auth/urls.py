from django.urls import path
from . import views

app_name = 'jwt_auth'

urlpatterns = [
    # Template view for token management
    path('', views.token_management_view, name='token_management'),
    
    # Generate JWT token (requires session authentication)
    path('generate/', views.GenerateJWTTokenAPIView.as_view(), name='generate_token'),
    
    # Verify JWT token (public endpoint)
    path('verify/', views.VerifyJWTTokenAPIView.as_view(), name='verify_token'),
    
    # Get public keys for token verification (public endpoint)
    path('keys/', views.PublicKeysAPIView.as_view(), name='public_keys'),
    
    # Revoke JWT token (requires session authentication)
    path('revoke/', views.RevokeJWTTokenAPIView.as_view(), name='revoke_token'),
    
    # List user's tokens (requires session authentication)
    path('tokens/', views.ListUserTokensAPIView.as_view(), name='list_tokens'),
    
    # List available scopes (requires session authentication)
    path('scopes/', views.ListScopesAPIView.as_view(), name='list_scopes'),
]
