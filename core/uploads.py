"""Direct browser-to-storage uploads (Uppy) with presigned URLs.

Uploads go straight from the browser to the S3-compatible endpoint (Backblaze
B2 in production) so file bytes never traverse the web process. The only
origin-side steps are:

1. ``sign_upload``: validates the request (auth scope, extension allowlist,
   size cap) and returns a short-lived presigned PUT URL for a server-generated
   key under ``DIRECT_UPLOAD_TMP_PREFIX``.
2. ``finalize_upload``: called when a model row is saved; verifies the temp
   object, copies it to a collision-free final key (server-side copy, no bytes
   through the app) and deletes the temp object.

Temporary objects that are never finalized are cleaned up by a bucket
lifecycle rule on the tmp prefix (see docs/dev/uploads.md).

The signing endpoint never trusts client-provided keys or names: keys are
always ``tmp/<32 hex>.<ext>`` and the extension is the only client-derived
fragment, validated against a per-scope allowlist. Finalization re-validates
the canonical key pattern, so the hidden-form payload cannot be used to copy
or delete arbitrary objects.
"""

import json
import re
import secrets

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage, storages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from storages.utils import clean_name

IMAGE_EXTENSIONS = {
    'jpg',
    'jpeg',
    'png',
    'webp',
}

DOCUMENT_EXTENSIONS = {
    'pdf',
    'doc',
    'docx',
    'docm',
    'xls',
    'xlsx',
    'ppt',
    'pptx',
    'txt',
    'csv',
    'odt',
    'ods',
    'odp',
    'zip',
    '7z',
    'rar',
    'gz',
    'tar',
}

# Per-upload-scope constraints. `compress` hints the client to downscale
# images before upload (photos only); the allowlist is enforced server-side
# regardless of what the client sends.
SCOPES = {
    'gallery': {
        'extensions': IMAGE_EXTENSIONS,
        'max_bytes': 100 * 1024 * 1024,
        'compress': True,
    },
    # Admin photo uploads: staff-gated, but image-only with client-side
    # compression like the public gallery flow.
    'gallery-admin': {
        'extensions': IMAGE_EXTENSIONS,
        'max_bytes': 100 * 1024 * 1024,
        'compress': True,
    },
    'exambank': {
        'extensions': DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS,
        'max_bytes': 200 * 1024 * 1024,
        'compress': False,
    },
    'admin': {
        'extensions': DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS,
        'max_bytes': 512 * 1024 * 1024,
        'compress': False,
    },
}

SIGNATURE_EXPIRES = 300  # seconds; presigned URLs are bearer tokens
TMP_KEY_PATTERN = re.compile(r'^tmp/([0-9a-f]{32})\.([a-z0-9]+)\Z')
MAX_FILES_PER_FORM = 1000


def uploads_enabled():
    """Direct uploads are only meaningful with S3-compatible storage."""
    return getattr(settings, 'USE_S3', False) and getattr(settings, 'DIRECT_UPLOADS_ENABLED', False)


def _storage_for_bucket(bucket):
    if bucket == 'public':
        return storages['public_media']
    return default_storage


def _check_scope_permission(request, scope):
    """Mirror the access gates of the existing upload views per scope."""
    if scope in ('gallery-admin', 'admin'):
        return bool(request.user.is_active and request.user.is_staff)
    if scope == 'gallery':
        return bool(request.user.is_authenticated) and (
            request.user.has_perm('gallery.add_album') or request.user.has_perm('archive.add_collection')
        )
    if scope == 'exambank':
        # Lazy import: exambank.views pulls in forms -> upload widgets -> this module.
        from exambank.views import exam_bank_access_is_allowed

        return exam_bank_access_is_allowed(request)
    return False


def _error(message, status):
    return JsonResponse({'error': message}, status=status)


@require_POST
def sign_upload(request):
    """Return a short-lived presigned PUT URL for a single file.

    Request fields: scope, bucket (private|public), name, size.
    Response: {method: 'PUT', url, key, expires}.
    """
    if not uploads_enabled():
        return _error('Direct uploads are not enabled.', 400)

    scope = request.POST.get('scope', '')
    scope_config = SCOPES.get(scope)
    if not scope_config:
        return _error('Unknown upload scope.', 400)

    try:
        if not _check_scope_permission(request, scope):
            raise PermissionDenied
    except PermissionDenied:
        return _error('Not allowed.', 403)

    bucket = request.POST.get('bucket', 'private')
    if bucket not in ('private', 'public'):
        return _error('Unknown bucket.', 400)

    name = request.POST.get('name', '')
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in scope_config['extensions']:
        return _error('File type not allowed.', 400)

    try:
        size = int(request.POST.get('size') or 0)
    except ValueError:
        return _error('Invalid file size.', 400)
    if not 0 < size <= scope_config['max_bytes']:
        return _error('File size not allowed.', 400)

    key = f"{settings.DIRECT_UPLOAD_TMP_PREFIX}{secrets.token_hex(16)}.{ext}"
    storage = _storage_for_bucket(bucket)
    url = storage.connection.meta.client.generate_presigned_url(
        'put_object',
        Params={'Bucket': storage.bucket_name, 'Key': key},
        ExpiresIn=SIGNATURE_EXPIRES,
    )
    return JsonResponse(
        {
            'method': 'PUT',
            'url': url,
            'key': key,
            'expires': SIGNATURE_EXPIRES,
            'compress': scope_config['compress'],
        }
    )


def _validated_temp_key(key, scope_config):
    """Return the key's extension when it matches the canonical temp pattern."""
    match = TMP_KEY_PATTERN.match(key) if isinstance(key, str) else None
    if not match:
        return None
    ext = match.group(2)
    if ext not in scope_config['extensions']:
        return None
    return ext


def parse_uploaded_files(value, scope=None):
    """Parse the hidden-field JSON written by the Uppy widget.

    Returns a list of dicts {key, name, size} where every key matches the
    canonical temp-key pattern and every declared size is within the scope's
    cap. Raises ValueError for malformed payloads. The canonical pattern check
    is the security boundary: temp keys are 128-bit random server-generated
    tokens, so matching keys cannot be forged or point at existing media.
    """
    scope_config = SCOPES.get(scope) if scope else None
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid upload payload.') from exc
    if not isinstance(parsed, list):
        raise ValueError('Invalid upload payload.')
    if len(parsed) > MAX_FILES_PER_FORM:
        raise ValueError('Too many files.')
    files = []
    for entry in parsed:
        if not isinstance(entry, dict) or not {'key', 'name', 'size'} <= set(entry):
            raise ValueError('Invalid upload payload.')
        key = entry['key']
        name = entry['name']
        size = entry['size']
        if not isinstance(key, str) or not isinstance(name, str):
            raise ValueError('Invalid upload payload.')
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size:
            raise ValueError('Invalid upload payload.')
        if scope_config is not None:
            if size > scope_config['max_bytes']:
                raise ValueError('File too large.')
            key_ext = _validated_temp_key(key, scope_config)
            name_ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            if key_ext is None or name_ext != key_ext:
                raise ValueError('Invalid upload payload.')
        files.append({'key': key, 'name': name, 'size': size})
    return files


def finalize_upload(temp_key, instance, field, filename, expected_size=None):
    """Move a direct-uploaded temp object to its final key.

    Verifies the temp key matches the canonical pattern, checks the stored
    object's size when an expected size is given, copies server-side within the
    same bucket (no bytes through the app) to a collision-free final key, then
    deletes the temp object. Returns the final storage name (relative to the
    storage location) for assignment to ``instance.<field>``.

    Raises ValueError when the object is missing or its size does not match;
    the temp object is left in place for the bucket lifecycle rule.
    """
    storage = field.storage
    client = storage.connection.meta.client
    bucket = storage.bucket_name

    if not isinstance(temp_key, str) or not TMP_KEY_PATTERN.match(temp_key):
        raise ValueError('Invalid upload key.')

    head = client.head_object(Bucket=bucket, Key=temp_key)
    actual_size = int(head.get('ContentLength', -1))
    if expected_size is not None and actual_size != expected_size:
        raise ValueError('Uploaded file size does not match.')

    name = field.generate_filename(instance, filename)
    name = storage.get_available_name(name, max_length=field.max_length or 100)
    full_key = storage._normalize_name(clean_name(name))  # noqa: SLF001 - storage API used by django-storages
    client.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': temp_key},
        Key=full_key,
    )
    client.delete_object(Bucket=bucket, Key=temp_key)
    return name
