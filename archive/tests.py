import os
import shutil
import tempfile

from PIL import Image

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from archive.models import TYPE_CHOICES, Collection, Document, Picture


def create_collection(title="Test collection", collection_type=None):
    return Collection.objects.create(title=title, pub_date=timezone.now(), type=collection_type)


def create_picture(favorite=False):
    collection = create_collection(collection_type=TYPE_CHOICES[0][1])
    img = Image.new('RGB', (100, 100))
    img.save(os.path.join(settings.MEDIA_ROOT, 'test_image.jpg'))
    img.close()
    img_file = open(os.path.join(settings.MEDIA_ROOT, 'test_image.jpg'),"rb")
    img_data = img_file.read()
    img_file.close()
    test_image = SimpleUploadedFile(name='test_image.jpg',
                                    content=img_data,
                                    content_type='image/jpg')
    return Picture.objects.create(collection=collection, image=test_image, favorite=favorite)


def create_document(title="Test document"):
    collection = create_collection(collection_type=TYPE_CHOICES[1][1])

    # Create a temporary file with some test data
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b'This is some test data for the document')
        temp_file.seek(0)  # Reset the file pointer to the beginning
        test_document = SimpleUploadedFile(name='test_document.doc', content=temp_file.read())

    return Document.objects.create(collection=collection, title=title, document=test_document)


class MediaRootMixin:
    @classmethod
    def setUpClass(cls):
        cls._temp_media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)


# models tests
class CollectionTestCase(MediaRootMixin, TestCase):
    def test_collection_creation(self):
        c = create_collection(collection_type=TYPE_CHOICES[0][1])
        self.assertTrue(isinstance(c, Collection))
        self.assertEqual(c.__str__(), c.title)
        self.assertEqual(c.type, TYPE_CHOICES[0][1])

    def test_picture_creation(self):
        p = create_picture(favorite=False)
        self.assertTrue(isinstance(p, Picture))
        self.assertEqual(p.__str__(), p.image.name)
        self.assertEqual(p.favorite, False)

    def test_document_creation(self):
        d = create_document()
        self.assertTrue(isinstance(d, Document))
        self.assertEqual(d.__str__(), d.title)
        self.assertEqual(d.collection.type, TYPE_CHOICES[1][1])
