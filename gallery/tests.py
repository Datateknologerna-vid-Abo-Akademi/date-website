import json
import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pillow_heif
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from PIL import Image

from members.models import ORDINARY_MEMBER, Member, MembershipType

from .admin import AlbumAdmin, PhotoInline
from .forms import AlbumAdminForm
from .models import Album, ImageProcessingError, Photo, compress_image


def _uploaded_image(name='upload.jpg'):
    image = Image.new('RGB', (100, 100), color=(25, 90, 140))
    image_bytes = BytesIO()
    image.save(image_bytes, format='JPEG')
    image.close()
    return SimpleUploadedFile(name=name, content=image_bytes.getvalue(), content_type='image/jpeg')


def _uploaded_heic_image(name='iphone-photo.heic'):
    image = Image.new('RGB', (100, 100), color=(90, 25, 140))
    heif_file = pillow_heif.from_pillow(image)
    image_bytes = BytesIO()
    heif_file.save(image_bytes, quality=50)
    return SimpleUploadedFile(name=name, content=image_bytes.getvalue(), content_type='image/heic')


def _corrupt_upload(name='broken.jpg'):
    return SimpleUploadedFile(name=name, content=b'not-actually-an-image', content_type='image/jpeg')


class CompressImageTests(TestCase):
    def test_raises_image_processing_error_for_undecodable_upload(self):
        with self.assertRaises(ImageProcessingError):
            compress_image(_corrupt_upload())

    def test_compresses_heic_upload_to_jpeg(self):
        result = compress_image(_uploaded_heic_image())

        self.assertTrue(result.name.endswith('.jpg'))
        self.assertEqual(result.content_type, 'image/jpeg')
        result.seek(0)
        decoded = Image.open(result)
        self.assertEqual(decoded.format, 'JPEG')


class AlbumAdminFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def test_creates_multi_uploads_after_saving_new_album(self):
        form = AlbumAdminForm(
            data={'title': 'Admin album', 'pub_date': '2026-08-23 14:00:00'},
            files=MultiValueDict({'images': [_uploaded_image('admin-upload.jpg')]}),
        )

        self.assertTrue(form.is_valid(), form.errors)
        album = form.save(commit=False)
        self.assertIsNone(album.pk)
        self.assertEqual(Photo.objects.count(), 0)

        album.save()
        form.save_m2m()

        photo = Photo.objects.get()
        self.assertEqual(photo.album, album)
        self.assertTrue(photo.image.name.endswith('admin-upload.jpg'))

    def test_creates_heic_upload_as_photo(self):
        form = AlbumAdminForm(
            data={'title': 'HEIC album', 'pub_date': '2026-08-23 14:00:00'},
            files=MultiValueDict({'images': [_uploaded_heic_image()]}),
        )

        self.assertTrue(form.is_valid(), form.errors)
        album = form.save(commit=False)
        album.save()
        form.save_m2m()

        photo = Photo.objects.get()
        self.assertEqual(photo.album, album)
        self.assertTrue(photo.image.name.endswith('.jpg'))
        self.assertEqual(form.skipped_images, [])

    def test_skips_unprocessable_image_and_keeps_valid_ones(self):
        form = AlbumAdminForm(
            data={'title': 'Mixed album', 'pub_date': '2026-08-23 14:00:00'},
            files=MultiValueDict({'images': [_uploaded_image('good.jpg'), _corrupt_upload('bad.jpg')]}),
        )

        self.assertTrue(form.is_valid(), form.errors)
        album = form.save(commit=False)
        album.save()
        form.save_m2m()

        self.assertEqual(Photo.objects.count(), 1)
        self.assertTrue(Photo.objects.get().image.name.endswith('good.jpg'))
        self.assertEqual(form.skipped_images, ['bad.jpg'])

    def test_skips_direct_upload_that_fails_finalize(self):
        payload = json.dumps([{'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'broken.jpg', 'size': 100}])
        with self.settings(USE_S3=True, DIRECT_UPLOADS_ENABLED=True):
            form = AlbumAdminForm(
                data={'title': 'Failing album', 'pub_date': '2026-08-23 14:00:00', 'images': payload},
            )
            self.assertTrue(form.is_valid(), form.errors)
            album = form.save(commit=False)
            album.save()
            with patch('core.uploads.finalize_upload', side_effect=ValueError('boom')):
                form.save_m2m()
        self.assertEqual(Photo.objects.count(), 0)
        self.assertEqual(form.skipped_images, ['broken.jpg'])


class GalleryLegacyAdminPermissionTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/admin/gallery/album/')
        self.request.user = SimpleNamespace(
            has_module_perms=Mock(return_value=False),
            has_perm=Mock(
                side_effect=lambda perm: (
                    perm
                    in {
                        'archive.view_picturecollection',
                        'archive.view_picture',
                        'archive.add_picture',
                        'archive.change_picture',
                        'archive.delete_picture',
                    }
                )
            ),
        )

    def test_legacy_permission_exposes_standard_admin_module(self):
        self.assertTrue(AlbumAdmin(Album, admin.site).has_module_permission(self.request))

    def test_legacy_permission_applies_to_photo_inline(self):
        inline = PhotoInline(Album, admin.site)

        self.assertTrue(inline.has_view_permission(self.request))
        self.assertTrue(inline.has_add_permission(self.request))
        self.assertTrue(inline.has_change_permission(self.request))
        self.assertTrue(inline.has_delete_permission(self.request))


class GalleryUploadViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='gallery_uploader',
            password='pwd',
            membership_type=membership_type,
        )
        cls.member.user_permissions.add(Permission.objects.get(codename='add_album', content_type__app_label='gallery'))

    def setUp(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_skips_unprocessable_image_and_keeps_valid_ones(self):
        response = self.client.post(
            reverse('archive:upload'),
            data={'album': 'Mixed upload', 'images': [_uploaded_image('good.jpg'), _corrupt_upload('bad.jpg')]},
        )

        self.assertEqual(response.status_code, 302)
        album = Album.objects.get(title='Mixed upload')
        self.assertEqual(Photo.objects.filter(album=album).count(), 1)
        self.assertTrue(Photo.objects.get(album=album).image.name.endswith('good.jpg'))

        response = self.client.get(reverse('archive:years'))
        warnings = [m.message for m in response.context['messages']]
        self.assertTrue(any('bad.jpg' in message for message in warnings))

    def test_accepts_heic_upload(self):
        response = self.client.post(
            reverse('archive:upload'),
            data={'album': 'HEIC upload', 'images': [_uploaded_heic_image()]},
        )

        self.assertEqual(response.status_code, 302)
        album = Album.objects.get(title='HEIC upload')
        photo = Photo.objects.get(album=album)
        self.assertTrue(photo.image.name.endswith('.jpg'))


@override_settings(USE_S3=True, DIRECT_UPLOADS_ENABLED=True)
class DirectUploadViewTests(TestCase):
    def setUp(self):
        self.user = Member.objects.create_user(username='uploader')
        permission = Permission.objects.get(codename='add_album', content_type__app_label='gallery')
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def test_direct_upload_creates_photos_from_temp_keys(self):
        payload = json.dumps([{'key': 'tmp/' + 'a' * 32 + '.jpg', 'name': 'photo.jpg', 'size': 12345}])
        with patch('core.uploads.finalize_upload', return_value='2026/test-album/photo.jpg') as finalize:
            response = self.client.post(reverse('archive:upload'), {'album': 'Test album', 'images': payload})

        self.assertRedirects(response, reverse('archive:years'))
        photo = Photo.objects.get()
        self.assertEqual(photo.album.title, 'Test album')
        self.assertEqual(photo.image.name, '2026/test-album/photo.jpg')
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args[0][0], 'tmp/' + 'a' * 32 + '.jpg')
        self.assertEqual(finalize.call_args[1]['expected_size'], 12345)

    def test_direct_upload_rejects_malformed_payload(self):
        response = self.client.post(
            reverse('archive:upload'),
            {
                'album': 'Test album',
                'images': json.dumps([{'key': 'media/2026/album/photo.jpg', 'name': 'photo.jpg', 'size': 1}]),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('images', response.context['picture_form'].errors)
        self.assertEqual(Album.objects.count(), 0)
        self.assertEqual(Photo.objects.count(), 0)

    def test_direct_upload_without_files_redirects_without_album(self):
        response = self.client.post(reverse('archive:upload'), {'album': 'Empty album'})
        self.assertRedirects(response, reverse('archive:years'))
        self.assertEqual(Album.objects.count(), 0)

    def test_classic_upload_still_works(self):
        image = Image.new('RGB', (100, 100))
        image_bytes = BytesIO()
        image.save(image_bytes, format='JPEG')
        image.close()
        upload = SimpleUploadedFile('classic.jpg', image_bytes.getvalue(), content_type='image/jpeg')

        with self.settings(USE_S3=False, DIRECT_UPLOADS_ENABLED=False):
            response = self.client.post(
                reverse('archive:upload'),
                {'album': 'Classic album', 'images': upload},
            )

        self.assertRedirects(response, reverse('archive:years'))
        photo = Photo.objects.get()
        self.assertTrue(photo.image.name.startswith('2026/classic-album/classic'))
