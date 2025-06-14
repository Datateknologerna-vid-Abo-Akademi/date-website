import os
from PIL import Image
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from archive.models import TYPE_CHOICES, Collection, Document, Picture
from django.urls import reverse
from members.models import Member
from archive.forms import PictureUploadForm
from django.utils.text import slugify


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


class PictureFormTestCase(TestCase):
    def test_slug_generated_from_album(self):
        form = PictureUploadForm(data={"album": "good/name"})
        self.assertTrue(form.is_valid())
        collection = Collection(title=form.cleaned_data["album"])
        collection.save()
        self.assertEqual(collection.slug, "goodname")

    def test_upload_invalid_album_returns_400(self):
        user = Member.objects.create_superuser(username="admin", password="pass")
        self.client.login(username="admin", password="pass")
        response = self.client.post(reverse("archive:upload"), {"album": "////"})
        self.assertEqual(response.status_code, 400)

# Views tests
    # https://realpython.com/testing-in-django-part-1-best-practices-and-examples/#testing-views
# Forms tests
    # https://realpython.com/testing-in-django-part-1-best-practices-and-examples/#testing-forms