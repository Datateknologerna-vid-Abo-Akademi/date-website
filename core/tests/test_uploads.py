import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import BotoCoreError, ClientError
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from redis.exceptions import ConnectionError as RedisConnectionError

from core import uploads
from core.upload_widgets import DirectUploadField
from gallery.models import Album, Photo
from members.models import Member

ENABLED = dict(USE_S3=True, DIRECT_UPLOADS_ENABLED=True)

JPEG_MAGIC = b'\xff\xd8\xff'


class FakeS3Client:
    def __init__(self):
        self.calls = []
        self.objects = {}

    def record(self, name, **kwargs):
        self.calls.append((name, kwargs))

    def generate_presigned_url(self, operation_name, Params=None, ExpiresIn=None, HttpMethod=None):
        self.record('presign', operation=operation_name, Params=Params, ExpiresIn=ExpiresIn)
        return 'https://s3.example.test/presigned-put'

    def _content(self, key):
        content = self.objects[key]
        if isinstance(content, int):
            return b'\x00' * content
        return content

    def _not_found(self, operation):
        return ClientError(
            {'Error': {'Code': '404', 'Message': 'Not Found'}, 'ResponseMetadata': {'HTTPStatusCode': 404}},
            operation,
        )

    def head_object(self, **kwargs):
        self.record('head_object', **kwargs)
        key = kwargs['Key']
        if key not in self.objects:
            raise self._not_found('HeadObject')
        return {'ContentLength': len(self._content(key))}

    def get_object(self, **kwargs):
        self.record('get_object', **kwargs)
        key = kwargs['Key']
        if key not in self.objects:
            raise self._not_found('GetObject')
        content = self._content(key)
        return {'Body': SimpleNamespace(read=lambda size: content[:size], close=lambda: None)}

    def copy_object(self, **kwargs):
        self.record('copy_object', **kwargs)
        self.objects[kwargs['Key']] = self.objects[kwargs['CopySource']['Key']]

    def delete_object(self, **kwargs):
        self.record('delete_object', **kwargs)
        self.objects.pop(kwargs['Key'], None)


class FakeS3Storage:
    bucket_name = 'date-private'
    location = 'media'
    default_acl = 'private'

    def __init__(self):
        self.client = FakeS3Client()
        self.connection = SimpleNamespace(meta=SimpleNamespace(client=self.client))
        self.existing_names = set()

    def _normalize_name(self, name):
        if self.location and not name.startswith(self.location):
            return os.path.join(self.location, name)
        return name

    def exists(self, name):
        return name in self.existing_names

    def get_available_name(self, name, max_length=None):
        if name not in self.existing_names:
            return name
        base, ext = os.path.splitext(name)
        counter = 1
        while f'{base}_{counter}{ext}' in self.existing_names:
            counter += 1
        return f'{base}_{counter}{ext}'

    def get_object_parameters(self, name):
        return {}


def create_user(username='uploader', **kwargs):
    return Member.objects.create_user(username=username, **kwargs)


def grant_gallery_upload(user):
    permission = Permission.objects.get(codename='add_album', content_type__app_label='gallery')
    user.user_permissions.add(permission)


def post_sign(client, **payload):
    return client.post(reverse('direct-upload-sign'), payload)


class SignUploadDisabledTests(TestCase):
    def test_returns_400_when_disabled(self):
        response = post_sign(
            self.client,
            scope='admin',
            bucket='private',
            name='test.jpg',
            size='100',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('not enabled', response.json()['error'])


@override_settings(**ENABLED)
class SignUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = FakeS3Storage()
        self.storage_patcher = patch('core.uploads._storage_for_bucket', return_value=self.storage)
        self.storage_patcher.start()
        self.addCleanup(self.storage_patcher.stop)

    def sign(self, **payload):
        defaults = {'scope': 'admin', 'bucket': 'private', 'name': 'test.jpg', 'size': '1024'}
        defaults.update(payload)
        return post_sign(self.client, **defaults)

    def test_sign_requires_csrf_token(self):
        response = Client(enforce_csrf_checks=True).post(
            reverse('direct-upload-sign'),
            {'scope': 'admin', 'bucket': 'private', 'name': 'test.jpg', 'size': '1024'},
        )
        self.assertEqual(response.status_code, 403)
        # The rejection must come from the CSRF middleware, not the view's own
        # permission gate (which would return JSON).
        self.assertIn(b'CSRF', response.content)
        self.assertNotEqual(response['Content-Type'].split(';')[0], 'application/json')

    def test_sign_rate_limited_per_user(self):
        staff = create_user(username='ratelimited', is_superuser=True)
        self.client.force_login(staff)
        with patch.dict(uploads.SIGN_RATE_LIMITS, {'admin': 3}):
            for _ in range(3):
                self.assertEqual(self.sign().status_code, 200)
            self.assertEqual(self.sign().status_code, 429)

    def test_sign_rate_limited_per_ip_for_anonymous(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        with patch.dict(uploads.SIGN_RATE_LIMITS, {'exambank': 2}):
            self.assertEqual(self.sign(scope='exambank').status_code, 200)
            self.assertEqual(self.sign(scope='exambank').status_code, 200)
            self.assertEqual(self.sign(scope='exambank').status_code, 429)

    def test_anonymous_rate_limit_is_per_session(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        other_client = Client()
        with patch.dict(uploads.SIGN_RATE_LIMITS, {'exambank': 1}):
            self.assertEqual(self.sign(scope='exambank').status_code, 200)
            self.assertEqual(self.sign(scope='exambank').status_code, 429)
            self.assertEqual(
                post_sign(
                    other_client,
                    scope='exambank',
                    bucket='private',
                    name='test.jpg',
                    size='1024',
                ).status_code,
                200,
            )

    def test_sign_rate_limits_are_per_scope(self):
        staff = create_user(username='scopeuser', is_superuser=True)
        self.client.force_login(staff)
        with patch.dict(uploads.SIGN_RATE_LIMITS, {'admin': 1, 'gallery-admin': 1}):
            self.assertEqual(self.sign().status_code, 200)
            self.assertEqual(self.sign(scope='gallery-admin').status_code, 200)

    def test_sign_rate_limit_fails_open_when_cache_unavailable(self):
        staff = create_user(username='cacheout', is_superuser=True)
        self.client.force_login(staff)

        class BrokenCache:
            def add(self, *args, **kwargs):
                raise RedisConnectionError('connection refused')

            def incr(self, *args, **kwargs):
                raise RedisConnectionError('connection refused')

        with patch('core.uploads.cache', BrokenCache()):
            response = self.sign()
        self.assertEqual(response.status_code, 200)

    def test_anonymous_requires_authentication(self):
        response = self.sign()
        self.assertEqual(response.status_code, 403)

    def test_admin_scope_requires_staff(self):
        member = create_user()
        self.client.force_login(member)
        response = self.sign()
        self.assertEqual(response.status_code, 403)

    def test_admin_scope_allows_staff(self):
        staff = create_user(username='staff', is_superuser=True)
        self.client.force_login(staff)
        response = self.sign()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['method'], 'PUT')

    def test_gallery_scope_requires_permission(self):
        member = create_user()
        self.client.force_login(member)
        response = self.sign(scope='gallery')
        self.assertEqual(response.status_code, 403)

        grant_gallery_upload(member)
        response = self.sign(scope='gallery')
        self.assertEqual(response.status_code, 200)

    def test_exambank_scope_uses_access_settings(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        member = create_user()
        self.client.force_login(member)
        response = self.sign(scope='exambank')
        self.assertEqual(response.status_code, 200)

    def test_exambank_scope_allows_anonymous_when_open(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        response = self.sign(scope='exambank')
        self.assertEqual(response.status_code, 200)

    def test_exambank_scope_requires_gate_when_signin_required(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=True)
        response = self.sign(scope='exambank')
        self.assertEqual(response.status_code, 403)

    def test_unknown_scope_rejected(self):
        staff = create_user(username='staff2', is_superuser=True)
        self.client.force_login(staff)
        response = self.sign(scope='nope')
        self.assertEqual(response.status_code, 400)

    def test_extension_allowlist_enforced(self):
        staff = create_user(username='staff3', is_superuser=True)
        self.client.force_login(staff)
        self.assertEqual(self.sign(name='evil.exe').status_code, 400)
        self.assertEqual(self.sign(name='photo.JPG').status_code, 200)
        self.assertEqual(self.sign(name='noextension').status_code, 400)

    def test_size_limits_enforced(self):
        staff = create_user(username='staff4', is_superuser=True)
        self.client.force_login(staff)
        self.assertEqual(self.sign(size='0').status_code, 400)
        self.assertEqual(self.sign(size='not-a-number').status_code, 400)
        admin_max = uploads.SCOPES['admin']['max_bytes']
        self.assertEqual(self.sign(size=str(admin_max + 1)).status_code, 400)
        self.assertEqual(self.sign(size=str(admin_max)).status_code, 200)

    def test_bucket_validated(self):
        staff = create_user(username='staff5', is_superuser=True)
        self.client.force_login(staff)
        response = self.sign(bucket='elsewhere')
        self.assertEqual(response.status_code, 400)

    def test_public_bucket_uses_public_storage(self):
        staff = create_user(username='staff6', is_superuser=True)
        self.client.force_login(staff)
        with patch('core.uploads._storage_for_bucket') as storage_for_bucket:
            storage_for_bucket.return_value = self.storage
            response = self.sign(bucket='public')
        self.assertEqual(response.status_code, 200)
        storage_for_bucket.assert_called_once_with('public')

    def test_non_admin_scopes_cannot_sign_public_bucket_uploads(self):
        from exambank.models import ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        self.assertEqual(self.sign(scope='exambank', bucket='public').status_code, 400)

        member = create_user(username='private-gallery')
        grant_gallery_upload(member)
        self.client.force_login(member)
        self.assertEqual(self.sign(scope='gallery', bucket='public').status_code, 400)

    def test_presigned_put_url_shape(self):
        staff = create_user(username='staff7', is_superuser=True)
        self.client.force_login(staff)
        response = self.sign(name='photo.jpg', size='2048')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['url'], 'https://s3.example.test/presigned-put')
        self.assertRegex(data['key'], uploads.TMP_KEY_PATTERN)
        self.assertTrue(data['key'].endswith('.jpg'))

        operation, params, expires = self.storage.client.calls[0][1].values()
        self.assertEqual(operation, 'put_object')
        self.assertEqual(params['Bucket'], 'date-private')
        self.assertEqual(params['Key'], data['key'])
        self.assertEqual(expires, uploads.SIGNATURE_EXPIRES)


@override_settings(**ENABLED)
class FinalizeUploadTests(TestCase):
    def setUp(self):
        self.album = Album.objects.create(title='Test album')
        self.storage = FakeS3Storage()
        self.storage.client.objects['tmp/abcdef1234567890abcdef1234567890.jpg'] = JPEG_MAGIC + b'\x00' * 97

    def _field(self):
        from django.core.files.storage import FileSystemStorage

        from gallery.models import upload_to

        class FakeField:
            storage = self.storage
            max_length = 100

            def __init__(self, upload_to):
                self.upload_to = upload_to

            def generate_filename(self, instance, filename):
                return FileSystemStorage().generate_filename(self.upload_to(instance, filename))

        return FakeField(upload_to)

    def test_copies_temp_to_final_key_and_deletes_temp(self):
        photo = Photo(album=self.album)
        final_name = uploads.finalize_upload(
            'tmp/abcdef1234567890abcdef1234567890.jpg',
            photo,
            self._field(),
            'My Photo.jpg',
            expected_size=100,
        )

        self.assertEqual(final_name, '2026/test-album/my-photo.jpg')
        calls = [call[0] for call in self.storage.client.calls]
        self.assertEqual(calls, ['head_object', 'get_object', 'copy_object', 'delete_object'])
        copy_call = self.storage.client.calls[2]
        self.assertEqual(copy_call[1]['Bucket'], 'date-private')
        self.assertEqual(
            copy_call[1]['CopySource'], {'Bucket': 'date-private', 'Key': 'tmp/abcdef1234567890abcdef1234567890.jpg'}
        )
        self.assertEqual(copy_call[1]['Key'], 'media/2026/test-album/my-photo.jpg')
        self.assertEqual(copy_call[1]['ACL'], 'private')
        delete_call = self.storage.client.calls[3]
        self.assertEqual(delete_call[1]['Key'], 'tmp/abcdef1234567890abcdef1234567890.jpg')

    def test_missing_temp_object_raises_value_error(self):
        photo = Photo(album=self.album)
        with self.assertRaisesRegex(ValueError, 'no longer exists'):
            uploads.finalize_upload(
                'tmp/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=100,
            )
        calls = [call[0] for call in self.storage.client.calls]
        self.assertEqual(calls, ['head_object'])
        self.assertNotIn('media/2026/test-album/photo.jpg', self.storage.client.objects)

    def test_transport_error_raising_botocore_error_raises_value_error(self):
        def broken_head(**kwargs):
            raise BotoCoreError()

        self.storage.client.head_object = broken_head
        photo = Photo(album=self.album)
        with self.assertRaisesRegex(ValueError, 'no longer exists'):
            uploads.finalize_upload(
                'tmp/abcdef1234567890abcdef1234567890.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=100,
            )
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)

    def test_copy_error_raises_value_error_and_keeps_temp_object(self):
        def broken_copy(**kwargs):
            raise ClientError(
                {'Error': {'Code': '500', 'Message': 'boom'}, 'ResponseMetadata': {'HTTPStatusCode': 500}},
                'CopyObject',
            )

        self.storage.client.copy_object = broken_copy
        photo = Photo(album=self.album)
        with self.assertRaisesRegex(ValueError, 'Could not finalize'):
            uploads.finalize_upload(
                'tmp/abcdef1234567890abcdef1234567890.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=100,
            )
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)

    def test_rejects_content_that_does_not_match_extension(self):
        self.storage.client.objects['tmp/abcdef1234567890abcdef1234567890.jpg'] = b'plain text, not a jpeg'
        photo = Photo(album=self.album)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            uploads.finalize_upload(
                'tmp/abcdef1234567890abcdef1234567890.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=len(b'plain text, not a jpeg'),
            )
        calls = [call[0] for call in self.storage.client.calls]
        self.assertEqual(calls, ['head_object', 'get_object'])
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)

    def test_rejects_non_temp_keys_without_side_effects(self):
        photo = Photo(album=self.album)
        with self.assertRaises(ValueError):
            uploads.finalize_upload('media/2026/other/photo.jpg', photo, self._field(), 'photo.jpg')
        self.assertEqual([call[0] for call in self.storage.client.calls], [])

    def test_magic_bytes_accepted_for_supported_extensions(self):
        cases = {
            'png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 20,
            'webp': b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 20,
            'pdf': b'%PDF-1.4\n' + b'\x00' * 20,
            'zip': b'PK\x03\x04' + b'\x00' * 20,
            'docx': b'PK\x03\x04' + b'\x00' * 20,
            'docm': b'PK\x03\x04' + b'\x00' * 20,
            'xlsx': b'PK\x03\x04' + b'\x00' * 20,
            'pptx': b'PK\x03\x04' + b'\x00' * 20,
            'odt': b'PK\x03\x04' + b'\x00' * 20,
            'ods': b'PK\x03\x04' + b'\x00' * 20,
            'odp': b'PK\x03\x04' + b'\x00' * 20,
            '7z': b'7z\xbc\xaf\x27\x1c' + b'\x00' * 20,
            'rar': b'Rar!\x1a\x07\x00' + b'\x00' * 20,
            'gz': b'\x1f\x8b\x08\x00' + b'\x00' * 20,
            'tar': b'\x00' * 257 + b'ustar' + b'\x00' * 20,
        }
        for ext, content in cases.items():
            with self.subTest(ext=ext):
                self.storage.client.calls.clear()
                key = f"tmp/{'b' * 32}.{ext}"
                self.storage.client.objects[key] = content
                photo = Photo(album=self.album)
                final_name = uploads.finalize_upload(
                    key,
                    photo,
                    self._field(),
                    f'file.{ext}',
                    expected_size=len(content),
                )
                self.assertTrue(final_name.endswith(f'.{ext}'))
                self.assertEqual(self.storage.client.calls[-1][0], 'delete_object')

    def test_magic_check_allows_extensions_without_signature(self):
        self.storage.client.objects['tmp/cccccccccccccccccccccccccccccccc.txt'] = b'any content at all'
        photo = Photo(album=self.album)
        final_name = uploads.finalize_upload(
            'tmp/cccccccccccccccccccccccccccccccc.txt',
            photo,
            self._field(),
            'notes.txt',
            expected_size=len(b'any content at all'),
        )
        self.assertTrue(final_name.endswith('.txt'))

    def test_unreadable_temp_object_raises_value_error(self):
        def broken_get_object(**kwargs):
            raise ClientError(
                {'Error': {'Code': '500', 'Message': 'boom'}, 'ResponseMetadata': {'HTTPStatusCode': 500}},
                'GetObject',
            )

        self.storage.client.get_object = broken_get_object
        photo = Photo(album=self.album)
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            uploads.finalize_upload(
                'tmp/abcdef1234567890abcdef1234567890.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=100,
            )
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)

    def test_delete_failure_does_not_block_finalize(self):
        def broken_delete_object(**kwargs):
            raise ClientError(
                {'Error': {'Code': '500', 'Message': 'boom'}, 'ResponseMetadata': {'HTTPStatusCode': 500}},
                'DeleteObject',
            )

        self.storage.client.delete_object = broken_delete_object
        photo = Photo(album=self.album)
        final_name = uploads.finalize_upload(
            'tmp/abcdef1234567890abcdef1234567890.jpg',
            photo,
            self._field(),
            'My Photo.jpg',
            expected_size=100,
        )
        self.assertEqual(final_name, '2026/test-album/my-photo.jpg')
        # Temp object is left for the lifecycle rule; the final copy exists.
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)
        self.assertIn('media/2026/test-album/my-photo.jpg', self.storage.client.objects)

    def test_rejects_size_mismatch_without_copy_or_delete(self):
        photo = Photo(album=self.album)
        with self.assertRaises(ValueError):
            uploads.finalize_upload(
                'tmp/abcdef1234567890abcdef1234567890.jpg',
                photo,
                self._field(),
                'photo.jpg',
                expected_size=999,
            )
        calls = [call[0] for call in self.storage.client.calls]
        self.assertEqual(calls, ['head_object'])
        self.assertIn('tmp/abcdef1234567890abcdef1234567890.jpg', self.storage.client.objects)

    def test_resolves_collisions_like_storage_does(self):
        self.storage.existing_names.add('2026/test-album/my-photo.jpg')
        photo = Photo(album=self.album)
        final_name = uploads.finalize_upload(
            'tmp/abcdef1234567890abcdef1234567890.jpg',
            photo,
            self._field(),
            'My Photo.jpg',
            expected_size=100,
        )
        self.assertEqual(final_name, '2026/test-album/my-photo_1.jpg')
        self.assertEqual(
            self.storage.client.calls[2][1]['Key'],
            'media/2026/test-album/my-photo_1.jpg',
        )


class ParseUploadedFilesTests(TestCase):
    def test_empty_and_absent_values(self):
        self.assertEqual(uploads.parse_uploaded_files(''), [])
        self.assertEqual(uploads.parse_uploaded_files(None), [])

    def test_valid_payload(self):
        payload = json.dumps(
            [
                {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 100},
                {'key': 'tmp/' + 'b' * 32 + '.pdf', 'name': 'doc.pdf', 'size': 200},
            ]
        )
        result = uploads.parse_uploaded_files(payload, scope='admin')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 100})
        self.assertEqual(result[1]['size'], 200)

    def test_rejects_empty_or_oversized_filename(self):
        key = 'tmp/' + 'a' * 32 + '.jpg'
        for name in ('', f"{'a' * 247}.jpg"):
            with self.assertRaisesRegex(ValueError, 'filename'):
                uploads.parse_uploaded_files(
                    json.dumps([{'key': key, 'name': name, 'size': 100}]),
                    scope='admin',
                )

    def test_scope_checks_extension_and_size(self):
        payload = json.dumps(
            [
                {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 100},
            ]
        )
        self.assertEqual(len(uploads.parse_uploaded_files(payload, scope='gallery')), 1)
        # Extension not allowed for the scope
        payload_exe = json.dumps(
            [
                {'key': 'tmp/' + 'a' * 32 + '.exe', 'name': 'photo.exe', 'size': 100},
            ]
        )
        with self.assertRaises(ValueError):
            uploads.parse_uploaded_files(payload_exe, scope='gallery')
        # Oversized for the scope
        payload_big = json.dumps(
            [
                {
                    'key': 'tmp/' + 'a' * 32 + '.jpg',
                    'name': 'photo.jpg',
                    'size': uploads.SCOPES['gallery']['max_bytes'] + 1,
                },
            ]
        )
        with self.assertRaises(ValueError):
            uploads.parse_uploaded_files(payload_big, scope='gallery')

    def test_canonical_key_pattern_enforced(self):
        # A key pointing at an existing media object must be rejected.
        for key in (
            'media/2026/album/photo.jpg',
            'public/2026/doc.pdf',
            'tmp/short.jpg',
            'tmp/' + 'A' * 32 + '.jpg',
            'tmp/' + 'a' * 32,
            '',
            'tmp/' + 'a' * 32 + '.jpg\n',
        ):
            payload = json.dumps([{'key': key, 'name': 'photo.jpg', 'size': 100}])
            with self.assertRaises(ValueError):
                uploads.parse_uploaded_files(payload, scope='admin')

    def test_missing_or_non_int_size_rejected(self):
        for entry in (
            {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg'},
            {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': '100'},
            {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 0},
        ):
            with self.assertRaises(ValueError):
                uploads.parse_uploaded_files(json.dumps([entry]), scope='admin')

    def test_invalid_payloads(self):
        for payload in (
            'not-json',
            '{"key": 1}',
            '[{"name": "no-key"}]',
            '[42]',
            '[{"key": 1, "name": "x.jpg", "size": 1}]',
        ):
            with self.assertRaises(ValueError):
                uploads.parse_uploaded_files(payload, scope='admin')

    def test_payload_without_scope_only_checks_shape(self):
        payload = json.dumps(
            [
                {'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 100},
            ]
        )
        self.assertEqual(len(uploads.parse_uploaded_files(payload)), 1)


@override_settings(**ENABLED)
class DirectUploadFallbackTests(TestCase):
    def test_direct_widget_renders_noscript_file_input(self):
        field = DirectUploadField(scope='gallery', multi=True)
        html = field.widget.render('images', None)
        self.assertIn('<noscript>', html)
        self.assertIn('type="file"', html)
        self.assertIn('multiple="multiple"', html)

    def test_direct_widget_accepts_multipart_fallback(self):
        field = DirectUploadField(scope='gallery', multi=True)
        uploaded = SimpleUploadedFile('photo.jpg', JPEG_MAGIC + b'content', content_type='image/jpeg')
        value = field.widget.value_from_datadict({}, MultiValueDict({'images': [uploaded]}), 'images')
        self.assertEqual(field.clean(value), [uploaded])
