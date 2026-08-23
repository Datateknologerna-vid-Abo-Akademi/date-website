import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.datastructures import MultiValueDict
from PIL import Image

from .forms import AlbumAdminForm
from .models import Photo


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
