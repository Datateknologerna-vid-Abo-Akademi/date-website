import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils.datastructures import MultiValueDict
from PIL import Image

from .admin import AlbumAdmin, PhotoInline
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
