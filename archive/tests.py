from django.test import TestCase
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from archive.models import Picture, Document, Collection, TYPE_CHOICES
import os


# models tests
class CollectionTestCase(TestCase):

    def create_collection(self, title="Test collection", collection_type=None):
        return Collection.objects.create(title=title, pub_date=timezone.now(), type=collection_type)

    def test_collection_creation(self):
        c = self.create_collection()
        self.assertTrue(isinstance(c, Collection))
        self.assertEqual(c.__str__(), c.title)
        self.assertEqual(c.type, TYPE_CHOICES[0])

    def create_picture(self, collection=create_collection(collection_type=TYPE_CHOICES[0]), favorite=False):
        test_image = SimpleUploadedFile(name='test_image.jpg',
                                        content=open(os.path.join(settings.MEDIA_ROOT, 'test_image.jpg'), 'rb').read(),
                                        content_type='image/jpeg')
        return Picture.objects.create(collection=collection, image=test_image, favorite=favorite)

    def test_picture_creation(self):
        p = self.create_picture()
        self.assertTrue(isinstance(p, Picture))
        self.assertEqual(p.__str__(), p.image.name)
        self.assertEqual(p.favorite, False)

    def create_document(self, collection=create_collection(collection_type=TYPE_CHOICES[1]), title="Test document"):
        test_document = SimpleUploadedFile(name='test_document.doc',
                                           content=open(os.path.join(settings.MEDIA_ROOT, 'test_document.doc')))
        return Document.objects.create(collection=collection, title=title, document=test_document)

    def test_document_creation(self):
        d = self.create_document()
        self.assertTrue(isinstance(d, Document))
        self.assertEqual(d.__str__(), d.title)
        self.assertEqual(d.collection.type, TYPE_CHOICES[1])
