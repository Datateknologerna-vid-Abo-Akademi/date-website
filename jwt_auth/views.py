"""
Django REST Framework API views for JWT Authentication
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import JWTKeyPair, JWTScope, JWTToken
from .permissions import JWTScopePermission
from .serializers import (
    TokenGenerateRequestSerializer,
    TokenGenerateResponseSerializer,
    TokenVerifyRequestSerializer,
    TokenVerifyResponseSerializer,
    PublicKeysResponseSerializer,
    TokenRevokeRequestSerializer,
    JWTTokenSerializer,
    JWTScopeSerializer
)

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
def token_management_view(request):
    """Template view for JWT token management interface"""
    return render(request, 'jwt_auth/token_management.html')


class GenerateJWTTokenAPIView(APIView):
    """
    API endpoint to generate JWT tokens for authenticated users
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Generate a new JWT token with specified scopes",
        request_body=TokenGenerateRequestSerializer,
        responses={
            200: TokenGenerateResponseSerializer,
            400: openapi.Response(description="Bad Request"),
            401: openapi.Response(description="Unauthorized"),
            500: openapi.Response(description="Internal Server Error"),
        },
        tags=['JWT Authentication']
    )
    def post(self, request):
        """Generate a new JWT token"""
        try:
            # Validate request data
            serializer = TokenGenerateRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            requested_scopes = validated_data.get('scopes', ['base'])
            expiry_hours = validated_data.get('expiry_hours', settings.JWT_DEFAULT_EXPIRY_HOURS)
            
            # Validate expiry hours
            max_expiry = settings.JWT_MAX_EXPIRY_HOURS
            if expiry_hours > max_expiry:
                return Response({
                    'error': f'Expiry hours cannot exceed {max_expiry} hours'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate scopes exist and are active
            available_scopes = JWTScope.objects.filter(
                name__in=requested_scopes,
                is_active=True
            )
            
            if available_scopes.count() != len(requested_scopes):
                invalid_scopes = set(requested_scopes) - set(
                    available_scopes.values_list('name', flat=True)
                )
                return Response({
                    'error': f'Invalid or inactive scopes: {list(invalid_scopes)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get active key pair
            key_pair = JWTKeyPair.get_active_keypair()
            if not key_pair:
                return Response({
                    'error': 'No active key pair available'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Create token record
            jwt_token = JWTToken.objects.create(
                user=request.user,
                key_pair=key_pair,
                expires_at=timezone.now() + timedelta(hours=expiry_hours)
            )
            jwt_token.scopes.set(available_scopes)
            
            # Generate JWT
            token_str = jwt_token.generate_token()
            
            response_data = {
                'token': token_str,
                'token_id': str(jwt_token.id),
                'expires_at': jwt_token.expires_at.isoformat(),
                'scopes': [scope.name for scope in available_scopes],
                'issued_at': jwt_token.created_at.isoformat()
            }
            
            logger.info(f"JWT token generated for user {request.user.id} with scopes {requested_scopes}")
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error generating JWT token: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyJWTTokenAPIView(APIView):
    """
    API endpoint to verify JWT tokens
    """
    authentication_classes = []  # Public endpoint
    permission_classes = []
    
    @swagger_auto_schema(
        operation_description="Verify a JWT token and return its claims",
        request_body=TokenVerifyRequestSerializer,
        responses={
            200: TokenVerifyResponseSerializer,
            400: openapi.Response(description="Bad Request"),
            401: openapi.Response(description="Unauthorized"),
        },
        tags=['JWT Authentication']
    )
    def post(self, request):
        """Verify a JWT token"""
        try:
            # Validate request data
            serializer = TokenVerifyRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            token = serializer.validated_data['token']
            
            # Verify token
            verification_result = JWTToken.verify_token(token)
            
            if not verification_result['valid']:
                return Response({
                    'valid': False,
                    'error': verification_result['error']
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            claims = verification_result['claims']
            token_obj = verification_result.get('token_obj')
            
            response_data = {
                'valid': True,
                'claims': claims,
                'user_id': claims.get('user_id'),
                'scopes': claims.get('scopes', []),
                'expires_at': datetime.fromtimestamp(claims['exp']).isoformat(),
                'issued_at': datetime.fromtimestamp(claims['iat']).isoformat(),
            }
            
            if token_obj:
                response_data['token_id'] = str(token_obj.id)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error verifying JWT token: {str(e)}")
            return Response({
                'valid': False,
                'error': 'Token verification failed'
            }, status=status.HTTP_401_UNAUTHORIZED)


class PublicKeysAPIView(APIView):
    """
    API endpoint to get public keys for JWT verification
    """
    authentication_classes = []  # Public endpoint
    permission_classes = []
    
    @swagger_auto_schema(
        operation_description="Get public keys for JWT token verification",
        responses={
            200: PublicKeysResponseSerializer,
        },
        tags=['JWT Authentication']
    )
    def get(self, request):
        """Get public keys in JWKS format"""
        try:
            keys = []
            for key_pair in JWTKeyPair.objects.filter(is_active=True):
                jwk = key_pair.get_public_jwk()
                if jwk:
                    keys.append(jwk)
            
            return Response({'keys': keys}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting public keys: {str(e)}")
            return Response({
                'error': 'Failed to retrieve public keys'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RevokeJWTTokenAPIView(APIView):
    """
    API endpoint to revoke JWT tokens
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Revoke a JWT token",
        request_body=TokenRevokeRequestSerializer,
        responses={
            200: openapi.Response(description="Token revoked successfully"),
            400: openapi.Response(description="Bad Request"),
            404: openapi.Response(description="Token not found"),
        },
        tags=['JWT Authentication']
    )
    def post(self, request):
        """Revoke a JWT token"""
        try:
            # Validate request data
            serializer = TokenRevokeRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': 'Invalid request data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            token_id = serializer.validated_data['token_id']
            
            # Find and revoke token
            try:
                jwt_token = JWTToken.objects.get(
                    id=token_id,
                    user=request.user,
                    is_revoked=False
                )
                jwt_token.revoke()
                
                logger.info(f"JWT token {token_id} revoked by user {request.user.id}")
                
                return Response({
                    'success': True,
                    'message': 'Token revoked successfully'
                }, status=status.HTTP_200_OK)
                
            except JWTToken.DoesNotExist:
                return Response({
                    'error': 'Token not found or already revoked'
                }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Error revoking JWT token: {str(e)}")
            return Response({
                'error': 'Failed to revoke token'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ListUserTokensAPIView(APIView):
    """
    API endpoint to list user's JWT tokens
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="List user's JWT tokens",
        responses={
            200: JWTTokenSerializer(many=True),
        },
        tags=['JWT Authentication']
    )
    def get(self, request):
        """List user's JWT tokens"""
        try:
            tokens = JWTToken.objects.filter(
                user=request.user
            ).select_related('key_pair').prefetch_related('scopes').order_by('-created_at')
            
            token_data = []
            for token in tokens:
                token_data.append({
                    'id': str(token.id),
                    'created_at': token.created_at.isoformat(),
                    'expires_at': token.expires_at.isoformat(),
                    'is_revoked': token.is_revoked,
                    'revoked_at': token.revoked_at.isoformat() if token.revoked_at else None,
                    'scopes': [scope.name for scope in token.scopes.all()],
                    'key_pair_id': str(token.key_pair.id) if token.key_pair else None,
                })
            
            return Response(token_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing user tokens: {str(e)}")
            return Response({
                'error': 'Failed to retrieve tokens'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ListScopesAPIView(APIView):
    """
    API endpoint to list available JWT scopes
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="List available JWT scopes",
        responses={
            200: JWTScopeSerializer(many=True),
        },
        tags=['JWT Authentication']
    )
    def get(self, request):
        """List available JWT scopes"""
        try:
            scopes = JWTScope.objects.filter(is_active=True)
            
            scope_data = []
            for scope in scopes:
                scope_data.append({
                    'name': scope.name,
                    'description': scope.description,
                    'is_active': scope.is_active,
                })
            
            return Response(scope_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing scopes: {str(e)}")
            return Response({
                'error': 'Failed to retrieve scopes'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
