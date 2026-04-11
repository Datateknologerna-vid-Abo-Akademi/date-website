import os
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

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

    def test_picture_image_url_uses_stored_image(self):
        collection = create_collection(collection_type=TYPE_CHOICES[0][0])
        picture = Picture(
            collection=collection,
            image=SimpleUploadedFile(
                name="gallery.webp",
                content=self._image_bytes("WEBP"),
                content_type="image/webp",
            ),
            original_filename="gallery.webp",
        )
        picture._skip_compression = True
        picture.save()

        self.assertTrue(picture.image_url.endswith(".webp"))
        self.assertEqual(picture.get_file_path(), picture.image_url)
        self.assertEqual(str(picture), "gallery.webp")

    def _image_bytes(self, fmt):
        image = Image.new('RGB', (100, 100), color=(10, 20, 30))
        image_bytes = BytesIO()
        image.save(image_bytes, format=fmt)
        image.close()
        return image_bytes.getvalue()

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


class PictureUploadApiTests(TestCase):
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
        cls.admin_user = Member.objects.create_superuser(
            username="archive_admin",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        cls.member = Member.objects.create_user(
            username="plain_member",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        cls.collection = create_collection(
            title="Upload Album",
            collection_type=TYPE_CHOICES[0][0],
        )
        cls.document_collection = create_collection(
            title="Documents",
            collection_type=TYPE_CHOICES[1][0],
        )

    def test_direct_upload_session_requires_permission(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("archive:picture_upload_direct"),
            data='{"collection_id": %d}' % self.collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)

    @override_settings(USE_S3=True)
    @patch("archive.views.create_presigned_temp_upload")
    def test_direct_upload_session_succeeds_for_authorized_user(self, create_presigned_temp_upload):
        create_presigned_temp_upload.return_value = {
            "upload_url": "https://s3.example.com/upload",
            "fields": {"key": "temp-key"},
            "temp_key": "temp/archive/temp-key.jpg",
        }
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("archive:picture_upload_direct"),
            data='{"collection_id": %d, "filename": "party.jpg", "content_type": "image/jpeg"}' % self.collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["temp_key"], "temp/archive/temp-key.jpg")

    def test_direct_upload_session_rejects_non_picture_collection(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("archive:picture_upload_direct"),
            data='{"collection_id": %d, "filename": "party.jpg", "content_type": "image/jpeg"}' % self.document_collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    @patch("archive.views.enqueue_task_on_commit")
    @patch("archive.views.head_temp_upload_object")
    def test_finalize_creates_processing_picture_from_temp_upload(self, head_temp_upload_object, enqueue_task_on_commit):
        head_temp_upload_object.return_value = {}
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("archive:picture_upload_complete"),
            data='{"collection_id": %d, "temp_key": "temp/archive/file-1.jpg", "filename": "party.jpg"}' % self.collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        picture = Picture.objects.get(temp_upload_key="temp/archive/file-1.jpg")
        self.assertEqual(picture.collection, self.collection)
        self.assertEqual(picture.upload_provider, Picture.UPLOAD_PROVIDER_S3_DIRECT)
        self.assertEqual(picture.processing_status, Picture.PROCESSING_STATUS_PENDING)
        enqueue_task_on_commit.assert_called_once()

    def test_finalize_rejects_duplicate_temp_keys(self):
        Picture.objects.create(
            collection=self.collection,
            upload_provider=Picture.UPLOAD_PROVIDER_S3_DIRECT,
            temp_upload_key="temp/archive/file-2.jpg",
            original_filename="existing.jpg",
            processing_status=Picture.PROCESSING_STATUS_PENDING,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("archive:picture_upload_complete"),
            data='{"collection_id": %d, "temp_key": "temp/archive/file-2.jpg", "filename": "existing.jpg"}' % self.collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["duplicate"])

    @patch("archive.views.head_temp_upload_object", side_effect=Exception("missing"))
    def test_finalize_rejects_missing_temp_uploads(self, _head_temp_upload_object):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("archive:picture_upload_complete"),
            data='{"collection_id": %d, "temp_key": "temp/archive/missing.jpg", "filename": "wait.jpg"}' % self.collection.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)

    @patch("archive.views.enqueue_task_on_commit")
    def test_fallback_upload_creates_local_picture_and_queues_optimization(self, enqueue_task_on_commit):
        self.client.force_login(self.admin_user)
        image = Image.new('RGB', (100, 100), color=(50, 50, 50))
        image_bytes = BytesIO()
        image.save(image_bytes, format='JPEG')
        image.close()

        response = self.client.post(
            reverse("archive:picture_upload_fallback"),
            data={
                "collection_id": self.collection.pk,
                "file": SimpleUploadedFile(
                    "fallback.jpg",
                    image_bytes.getvalue(),
                    content_type="image/jpeg",
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        picture = Picture.objects.get(pk=response.json()["picture_id"])
        self.assertEqual(picture.upload_provider, Picture.UPLOAD_PROVIDER_LOCAL)
        self.assertEqual(picture.original_filename, "fallback.jpg")
        self.assertEqual(picture.processing_status, Picture.PROCESSING_STATUS_PENDING)
        enqueue_task_on_commit.assert_called_once()
