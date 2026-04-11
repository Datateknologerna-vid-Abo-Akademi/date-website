import os
import shutil
import tempfile
from io import BytesIO

from PIL import Image

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from archive.models import TYPE_CHOICES, Collection, Document, Picture
from members.models import Member, MembershipType, ORDINARY_MEMBER


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


class PictureDetailFragmentViewTests(TestCase):
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
        cls.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='archive_user',
            password='pwd',
            membership_type=cls.membership_type,
        )
        cls.collection = create_collection(
            title='Fragment Album',
            collection_type=TYPE_CHOICES[0][0],
        )

    def setUp(self):
        for index in range(13):
            Picture.objects.create(
                collection=self.collection,
                image=self._uploaded_image(f'fragment-{index}.jpg'),
            )

    def _uploaded_image(self, name):
        image = Image.new('RGB', (100, 100), color=(25, 90, 140))
        image_bytes = BytesIO()
        image.save(image_bytes, format='JPEG')
        image.close()
        return SimpleUploadedFile(
            name=name,
            content=image_bytes.getvalue(),
            content_type='image/jpeg',
        )

    def test_fragment_response_returns_gallery_payload_for_authenticated_member(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(self._detail_url(), {'page': 2, 'fragment': '1'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {'html', 'has_next', 'next_page', 'page', 'start_index', 'total_count'},
        )
        self.assertEqual(payload['page'], 2)
        self.assertEqual(payload['start_index'], 13)
        self.assertEqual(payload['total_count'], 13)
        self.assertFalse(payload['has_next'])
        self.assertIsNone(payload['next_page'])
        self.assertIn('data-global-index="13"', payload['html'])
        self.assertIn('class="grid-item glightbox"', payload['html'])

    def test_fragment_response_keeps_album_images_in_upload_order(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(self._detail_url(), {'page': 1, 'fragment': '1'})

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertLess(html.index('fragment-0.jpg'), html.index('fragment-1.jpg'))
        self.assertLess(html.index('fragment-10.jpg'), html.index('fragment-11.jpg'))

    def test_fragment_response_redirects_anonymous_users_to_login(self):
        response = self.client.get(self._detail_url(), {'page': 1, 'fragment': '1'})

        self.assertEqual(response.status_code, 302)
        self.assertIn('/members/login/', response['Location'])

    def _detail_url(self):
        return reverse(
            'archive:detail',
            kwargs={
                'year': self.collection.pub_date.year,
                'album': self.collection.title,
            },
        )
