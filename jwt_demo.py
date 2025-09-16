#!/usr/bin/env python3
"""
JWT Token Example Script

This script demonstrates the JWT token functionality without requiring Django database setup.
It shows how to generate RSA key pairs and create/verify JWT tokens.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt


def generate_rsa_key_pair():
    """Generate an RSA key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
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
    
    return private_key, public_key, private_pem, public_pem


def create_jwt_token(private_key, user_data, expires_in_hours=24):
    """Create a JWT token with user data"""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expires_in_hours)
    
    payload = {
        'user_id': user_data.get('user_id', 1),
        'username': user_data.get('username', 'demo_user'),
        'email': user_data.get('email', 'demo@example.com'),
        'membership_type': user_data.get('membership_type', 'ORDINARY_MEMBER'),
        'iat': now,
        'exp': expires_at,
        'iss': 'date-website',
        'aud': 'date-website-api',
        'jti': str(uuid.uuid4())
    }
    
    token = jwt.encode(
        payload,
        private_key,
        algorithm='RS256',
        headers={'kid': 'demo-key'}
    )
    
    return token, payload


def verify_jwt_token(token, public_key):
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience='date-website-api',
            issuer='date-website'
        )
        return payload, True
    except jwt.InvalidTokenError as e:
        return str(e), False


def main():
    print("=== JWT Token Demo for Date Website ===\n")
    
    # Generate key pair
    print("1. Generating RSA key pair...")
    private_key, public_key, private_pem, public_pem = generate_rsa_key_pair()
    print("✓ Key pair generated successfully\n")
    
    # Display public key
    print("2. Public key (PEM format):")
    print(public_pem)
    
    # Create demo user data
    user_data = {
        'user_id': 123,
        'username': 'john_doe',
        'email': 'john.doe@example.com',
        'membership_type': 'ORDINARY_MEMBER'
    }
    
    # Generate JWT token
    print("3. Generating JWT token for user:", user_data['username'])
    token, payload = create_jwt_token(private_key, user_data)
    print("✓ Token generated successfully")
    print(f"Token length: {len(token)} characters")
    print(f"Token: {token[:50]}...{token[-50:]}\n")
    
    # Display payload
    print("4. Token payload:")
    print(json.dumps(payload, indent=2, default=str))
    print()
    
    # Verify token
    print("5. Verifying JWT token...")
    decoded_payload, is_valid = verify_jwt_token(token, public_key)
    
    if is_valid:
        print("✓ Token verification successful!")
        print("Decoded payload:")
        print(json.dumps(decoded_payload, indent=2, default=str))
    else:
        print("✗ Token verification failed!")
        print("Error:", decoded_payload)
    
    print("\n=== Demo completed ===")
    
    # API Usage Examples
    print("\n=== API Usage Examples ===")
    print("\n1. Generate Token (POST /api/jwt/generate/):")
    print("curl -X POST http://localhost:8000/api/jwt/generate/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -H 'X-CSRFToken: YOUR_CSRF_TOKEN' \\")
    print("  -d '{\"purpose\": \"api_access\", \"expires_in_hours\": 24}' \\")
    print("  --cookie 'sessionid=YOUR_SESSION_ID'")
    
    print("\n2. Verify Token (POST /api/jwt/verify/):")
    print("curl -X POST http://localhost:8000/api/jwt/verify/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"token\": \"YOUR_JWT_TOKEN\"}'")
    
    print("\n3. Get Public Keys (GET /api/jwt/keys/):")
    print("curl http://localhost:8000/api/jwt/keys/")
    
    print("\n4. List User Tokens (GET /api/jwt/tokens/):")
    print("curl http://localhost:8000/api/jwt/tokens/ \\")
    print("  --cookie 'sessionid=YOUR_SESSION_ID'")
    
    print("\n5. Revoke Token (POST /api/jwt/revoke/):")
    print("curl -X POST http://localhost:8000/api/jwt/revoke/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -H 'X-CSRFToken: YOUR_CSRF_TOKEN' \\")
    print("  -d '{\"token_id\": \"YOUR_TOKEN_ID\"}' \\")
    print("  --cookie 'sessionid=YOUR_SESSION_ID'")


if __name__ == "__main__":
    main()
