import os

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image

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
    doc_file = open(os.path.join(settings.MEDIA_ROOT, 'test_document.doc'), "rb")
    doc_data = doc_file.read()
    doc_file.close()
    test_document = SimpleUploadedFile(name='test_document.doc',
                                        content=doc_data)
    return Document.objects.create(collection=collection, title=title, document=test_document)


# models tests
class CollectionTestCase(TestCase):
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

# Views tests
    # https://realpython.com/testing-in-django-part-1-best-practices-and-examples/#testing-views
# Forms tests
    # https://realpython.com/testing-in-django-part-1-best-practices-and-examples/#testing-forms