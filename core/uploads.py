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

Sign requests are rate limited per user/IP, and finalized objects get a
server-side magic-byte check matching the declared extension, so mislabeled
content never reaches the final media paths.
"""

import json
import logging
import re
import secrets

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage, storages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from storages.utils import clean_name

logger = logging.getLogger('date')

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

# Fixed-window rate limit on the signing endpoint. Authenticated users are
# keyed by user id; anonymous visitors (e.g. an open exam bank) are keyed by
# REMOTE_ADDR, which behind the load balancer is the proxy address, so
# anonymous requests share one bucket per deployment. Staff scopes get a
# higher cap because bulk admin uploads sign one URL per file.
SIGN_RATE_LIMITS = {
    'gallery': 120,
    'gallery-admin': 600,
    'exambank': 120,
    'admin': 600,
}
SIGN_RATE_LIMIT = 60  # fallback for unknown scopes
SIGN_RATE_WINDOW_SECONDS = 60

# Magic-byte signatures verified server-side at finalize for extensions with a
# stable header. Alternatives are OR'd; within one alternative every (offset,
# magic) pair must match. Extensions without an entry (txt, csv, legacy
# binary office formats) are allowed through unchecked.
_MAGIC_SIGNATURES = {
    'jpg': (((0, b'\xff\xd8\xff'),),),
    'jpeg': (((0, b'\xff\xd8\xff'),),),
    'png': (((0, b'\x89PNG\r\n\x1a\n'),),),
    'webp': (((0, b'RIFF'), (8, b'WEBP')),),
    'gif': (((0, b'GIF8'),),),
    'pdf': (((0, b'%PDF'),),),
    # ZIP containers: zip itself plus the OOXML/ODF office extensions.
    'zip': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'docx': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'docm': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'xlsx': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'pptx': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'odt': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'ods': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    'odp': (
        ((0, b'PK\x03\x04'),),
        ((0, b'PK\x05\x06'),),
        ((0, b'PK\x07\x08'),),
    ),
    '7z': (((0, b'7z\xbc\xaf\x27\x1c'),),),
    'rar': (((0, b'Rar!\x1a\x07'),),),
    'gz': (((0, b'\x1f\x8b'),),),
    'tar': (((257, b'ustar'),),),
}
_MAGIC_READ_BYTES = 512


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


def _sign_rate_allowed(request, scope):
    """Fixed-window counter in the cache; bounds sign calls per user/IP.

    Fails open when the cache backend is unavailable so an outage never blocks
    all uploads.
    """
    limit = SIGN_RATE_LIMITS.get(scope, SIGN_RATE_LIMIT)
    if request.user.is_authenticated:
        key = f'upload-sign:user:{request.user.pk}'
    else:
        key = f"upload-sign:ip:{request.META.get('REMOTE_ADDR') or 'unknown'}"
    try:
        if cache.add(key, 1, SIGN_RATE_WINDOW_SECONDS):
            return True
        try:
            count = cache.incr(key)
        except ValueError:
            # Key expired between add and incr; start a fresh window.
            cache.set(key, 1, SIGN_RATE_WINDOW_SECONDS)
            return True
    except ConnectionError, OSError:
        return True
    return count <= limit


def _verify_magic_bytes(client, bucket, key, ext):
    """Check the object's first bytes against the signature table for ``ext``.

    Reads only the first few hundred bytes (a ranged GET), so file bytes never
    traverse the app. Raises ValueError when the content does not match the
    declared extension; extensions without a known signature pass.
    """
    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        return
    response = None
    try:
        response = client.get_object(Bucket=bucket, Key=key, Range=f'bytes=0-{_MAGIC_READ_BYTES - 1}')
        head = response['Body'].read(_MAGIC_READ_BYTES)
    except (ClientError, BotoCoreError) as exc:
        raise ValueError(f'Temporary upload is unreadable: {key}') from exc
    finally:
        if response is not None:
            response['Body'].close()
    for alternative in signatures:
        if all(head[offset : offset + len(magic)] == magic for offset, magic in alternative):
            return
    raise ValueError('File content does not match its declared type.')


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

    # Count only requests that passed the scope gate, so unauthorized junk
    # cannot exhaust the bucket.
    if not _sign_rate_allowed(request, scope):
        return _error('Too many upload requests, try again later.', 429)

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
    object's size when an expected size is given, verifies the content's magic
    bytes against the declared extension, copies server-side within the same
    bucket (no bytes through the app) to a collision-free final key, then
    deletes the temp object. Returns the final storage name (relative to the
    storage location) for assignment to ``instance.<field>``.

    The temp object must live on the same storage as the model field: the
    form's ``bucket`` (private|public) must match the storage backing the
    field (private -> default storage, public -> ``public_media``). The copy
    mirrors django-storages' write parameters (ACL + object parameters), so
    public-bucket copies keep ``public-read``.

    Raises ValueError when the object is missing, its size does not match, or
    its content does not match the declared type; the temp object is left in
    place for the bucket lifecycle rule.
    """
    storage = field.storage
    client = storage.connection.meta.client
    bucket = storage.bucket_name

    match = TMP_KEY_PATTERN.match(temp_key) if isinstance(temp_key, str) else None
    if not match:
        raise ValueError('Invalid upload key.')
    key_ext = match.group(2)

    try:
        head = client.head_object(Bucket=bucket, Key=temp_key)
    except (ClientError, BotoCoreError) as exc:
        raise ValueError(f'Temporary upload no longer exists: {temp_key}') from exc
    actual_size = int(head.get('ContentLength', -1))
    if expected_size is not None and actual_size != expected_size:
        raise ValueError('Uploaded file size does not match.')

    _verify_magic_bytes(client, bucket, temp_key, key_ext)

    name = field.generate_filename(instance, filename)
    name = storage.get_available_name(name, max_length=field.max_length or 100)
    full_key = storage._normalize_name(clean_name(name))  # noqa: SLF001 - storage API used by django-storages
    copy_params = {
        'Bucket': bucket,
        'CopySource': {'Bucket': bucket, 'Key': temp_key},
        'Key': full_key,
    }
    copy_params.update(storage.get_object_parameters(full_key))
    if 'ACL' not in copy_params and getattr(storage, 'default_acl', None):
        copy_params['ACL'] = storage.default_acl
    client.copy_object(**copy_params)
    try:
        client.delete_object(Bucket=bucket, Key=temp_key)
    except (ClientError, BotoCoreError) as exc:
        # The final object is already in place; the temp object is left for
        # the bucket lifecycle rule.
        logger.warning('Could not delete temp upload %s: %s', temp_key, exc)
    return name
