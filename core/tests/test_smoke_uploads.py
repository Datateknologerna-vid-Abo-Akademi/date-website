from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from members.models import Member


@override_settings(USE_S3=True, DIRECT_UPLOADS_ENABLED=True)
class DirectUploadSmokeTests(TestCase):
    """Render-level smoke checks: widgets and assets appear when direct
    uploads are enabled and disappear when disabled."""

    def setUp(self):
        self.user = Member.objects.create_superuser(username='smoke-admin', password='pwd', email='a@example.com')
        self.client.force_login(self.user)

    def test_admin_album_add_renders_direct_widget(self):
        response = self.client.get(reverse('admin:gallery_album_add'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-uppy-widget="1"', html)
        self.assertIn('https://releases.transloadit.com/uppy/v5.2.4/uppy.min.js', html)
        self.assertIn('data-uppy-scope="gallery-admin"', html)
        self.assertIn('data-uppy-compress="true"', html)

    def test_public_upload_page_renders_widget(self):
        album_perm = Permission.objects.get(codename='add_album', content_type__app_label='gallery')
        self.user.user_permissions.add(album_perm)
        response = self.client.get(reverse('archive:upload'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-uppy-widget="1"', html)
        self.assertIn('https://releases.transloadit.com/uppy/v5.2.4/uppy.min.js', html)
        self.assertIn('integrity="sha384-hl+zw0fpZ6cVAtnkwy96IFC3oGXSYqe8', html)
        self.assertIn('data-uppy-scope="gallery"', html)
        self.assertIn('data-uppy-compress="true"', html)

    def test_admin_archive_document_add_renders_widget(self):
        response = self.client.get(reverse('admin:archive_documentcollection_add'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-uppy-widget="1"', html)
        self.assertIn('data-uppy-bucket="private"', html)

    def test_exam_admin_renders_widget(self):
        response = self.client.get(reverse('admin:exambank_examarchive_add'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-uppy-widget="1"', html)

    def test_public_exam_upload_page_renders_widget(self):
        from exambank.models import ExamArchive, ExamBankAccessSettings

        ExamBankAccessSettings.objects.create(require_sign_in=False)
        archive = ExamArchive.objects.create(title='Math 1')
        response = self.client.get(reverse('archive:exam_upload', args=[archive.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-uppy-widget="1"', html)
        self.assertIn('data-uppy-scope="exambank"', html)

    def test_assets_absent_when_disabled(self):
        album_perm = Permission.objects.get(codename='add_album', content_type__app_label='gallery')
        self.user.user_permissions.add(album_perm)
        with self.settings(USE_S3=False, DIRECT_UPLOADS_ENABLED=False):
            response = self.client.get(reverse('archive:upload'))
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertNotIn('uppy.min.js', html)
            self.assertNotIn('data-uppy-widget', html)

            admin_response = self.client.get(reverse('admin:gallery_album_add'))
            self.assertNotIn('uppy.min.js', admin_response.content.decode())
            self.assertNotIn('data-uppy-widget', admin_response.content.decode())


@override_settings(USE_S3=False, DIRECT_UPLOADS_ENABLED=False)
class ClassicModeSmokeTests(TestCase):
    def setUp(self):
        self.user = Member.objects.create_superuser(username='smoke-admin2', password='pwd', email='b@example.com')
        self.client.force_login(self.user)

    def test_upload_page_uses_classic_input_when_disabled(self):
        album_perm = Permission.objects.get(codename='add_album', content_type__app_label='gallery')
        self.user.user_permissions.add(album_perm)
        response = self.client.get(reverse('archive:upload'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('type="file"', html)
        self.assertNotIn('data-uppy-widget', html)
