# JWT Authentication Maintenance Tasks

This document describes the Celery-based maintenance tasks for the JWT authentication system.

## Overview

The JWT authentication system includes several automated maintenance tasks that run periodically to ensure security and performance:

1. **Token Cleanup**: Removes expired tokens from the database
2. **Key Rotation**: Automatically rotates JWT signing keys
3. **Health Monitoring**: Generates system health reports
4. **Scope Initialization**: Ensures default scopes exist

## Automatic Tasks (Celery Beat)

### cleanup_expired_tokens
- **Schedule**: Daily
- **Purpose**: Marks expired tokens as revoked and deletes very old tokens
- **Configuration**: Tokens older than 90 days are permanently deleted

### rotate_jwt_keypairs
- **Schedule**: Weekly
- **Purpose**: Rotates JWT signing keys for security
- **Configuration**: 
  - `JWT_KEYPAIR_ROTATION_DAYS`: Days before rotation (default: 30)
  - `JWT_MAX_ACTIVE_KEYPAIRS`: Maximum active keypairs (default: 3)

### cleanup_inactive_keypairs
- **Schedule**: Monthly
- **Purpose**: Removes very old inactive keypairs with no associated tokens
- **Configuration**: `JWT_KEYPAIR_CLEANUP_DAYS`: Days before cleanup (default: 180)

### generate_jwt_health_report
- **Schedule**: Daily
- **Purpose**: Generates health reports for monitoring
- **Output**: Logs system statistics and health status

### initialize_jwt_scopes
- **Schedule**: Weekly
- **Purpose**: Ensures default scopes exist in the system
- **Default Scopes**:
  - `base`: Basic access to authenticated endpoints
  - `image_upload`: Permission to upload images and media files
  - `event_management`: Permission to create and manage events
  - `admin`: Full administrative access

## Manual Management

### Django Management Commands

Use the `jwt_manage` command for manual operations:

```bash
# Initialize the JWT system (create keypairs and scopes)
python manage.py jwt_manage init

# Run token cleanup manually
python manage.py jwt_manage cleanup

# Force keypair rotation
python manage.py jwt_manage rotate --force

# Generate health report
python manage.py jwt_manage health

# Show current system status
python manage.py jwt_manage status

# Create a new keypair
python manage.py jwt_manage create-keypair

# Create default scopes
python manage.py jwt_manage create-scopes

# Clean up old keypairs
python manage.py jwt_manage cleanup-keypairs
```

### Direct Task Execution

You can also run tasks directly using Celery:

```python
from jwt_auth.tasks import (
    cleanup_expired_tokens,
    rotate_jwt_keypairs,
    generate_jwt_health_report
)

# Run cleanup
result = cleanup_expired_tokens.delay()
print(result.get())

# Force rotation
result = rotate_jwt_keypairs.delay()
print(result.get())

# Generate health report
result = generate_jwt_health_report.delay()
print(result.get())
```

## Configuration

### Environment Variables

- `JWT_KEYPAIR_ROTATION_DAYS`: Days between key rotations (default: 30)
- `JWT_MAX_ACTIVE_KEYPAIRS`: Maximum number of active keypairs (default: 3)
- `JWT_KEYPAIR_CLEANUP_DAYS`: Days before cleaning up old keypairs (default: 180)

### Settings

Add these to your Django settings:

```python
# JWT Authentication Task Settings
JWT_KEYPAIR_ROTATION_DAYS = 30
JWT_MAX_ACTIVE_KEYPAIRS = 3
JWT_KEYPAIR_CLEANUP_DAYS = 180

# Celery Beat Schedule (already configured)
CELERY_BEAT_SCHEDULE = {
    # ... (see core/settings/common.py)
}
```

## Monitoring

### Health Reports

The system generates daily health reports that include:

- Token statistics (total, active, expired, revoked)
- Keypair status (active, inactive counts)
- Recent activity (tokens created in last 24h)
- Overall health status

### Logging

All maintenance tasks log their activities. Check the application logs for:

- Task execution results
- Error messages
- Security events (key rotations, etc.)

### Manual Health Check

```bash
python manage.py jwt_manage health
```

This will show a detailed health report including:
- Current keypair status
- Token statistics
- Scope availability
- Overall system health

## Security Considerations

1. **Key Rotation**: Keys are rotated automatically every 30 days by default
2. **Token Cleanup**: Expired tokens are marked as revoked, maintaining audit trail
3. **Multiple Active Keys**: System maintains multiple active keypairs for seamless rotation
4. **Monitoring**: Regular health checks ensure system integrity

## Troubleshooting

### No Active Keypairs
```bash
python manage.py jwt_manage create-keypair
```

### Missing Scopes
```bash
python manage.py jwt_manage create-scopes
```

### Force Key Rotation
```bash
python manage.py jwt_manage rotate --force
```

### Check System Status
```bash
python manage.py jwt_manage status
```

## Production Deployment

1. Ensure Celery Beat is running for automatic tasks
2. Configure appropriate task schedules in settings
3. Set up monitoring for task failures
4. Review logs regularly for security events
5. Consider adjusting rotation schedules based on security requirements
