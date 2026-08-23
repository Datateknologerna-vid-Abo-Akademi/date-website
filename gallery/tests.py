import json
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from PIL import Image

from members.models import Member

from .forms import AlbumAdminForm
from .models import Album, Photo


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
            files=MultiValueDict({'images': [self._uploaded_image('admin-upload.jpg')]}),
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

    def _uploaded_image(self, name):
        image = Image.new('RGB', (100, 100), color=(25, 90, 140))
        image_bytes = BytesIO()
        image.save(image_bytes, format='JPEG')
        image.close()
        return SimpleUploadedFile(name=name, content=image_bytes.getvalue(), content_type='image/jpeg')


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
        self.assertRedirects(response, reverse('archive:years'))
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
