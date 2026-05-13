import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from exambank.forms import ExamArchiveAdminForm
from exambank.models import ExamArchive, ExamFile
from members.models import Member, MembershipType, ORDINARY_MEMBER


class ExamBankArchiveRouteTests(TestCase):
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

    def setUp(self):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='exam-user',
            password='pwd',
            membership_type=membership_type,
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_legacy_archive_exams_index_renders_archives(self):
        ExamArchive.objects.create(title='Algorithms')

        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Algorithms')

    def test_legacy_archive_exams_detail_renders_exam_files(self):
        archive = ExamArchive.objects.create(title='Databases')
        ExamFile.objects.create(
            archive=archive,
            title='tent 01.01.2024',
            document=SimpleUploadedFile('database.pdf', b'pdf'),
        )

        response = self.client.get(reverse('archive:exams_detail', args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Databases')
        self.assertContains(response, 'tent 01.01.2024')

    def test_legacy_archive_exam_upload_adds_files(self):
        archive = ExamArchive.objects.create(
            title='Networks',
            pub_date=timezone.datetime(2024, 1, 1, tzinfo=timezone.UTC),
        )

        response = self.client.post(
            reverse('archive:exam_upload', args=[archive.pk]),
            {
                'title': 'tent 02.02.2024',
                'exam': SimpleUploadedFile('networks.pdf', b'pdf'),
            },
        )

        self.assertRedirects(response, reverse('archive:exams_detail', args=[archive.pk]))
        exam_file = ExamFile.objects.get(archive=archive)
        self.assertEqual(exam_file.title, 'tent 02.02.2024')
        self.assertEqual(exam_file.document.name, '2024/networks/networks.pdf')

    def test_legacy_archive_exam_archive_upload_adds_archive(self):
        response = self.client.post(
            reverse('archive:exam_archive_upload'),
            {'title': 'Compilers'},
        )

        self.assertRedirects(response, reverse('archive:exams'))
        self.assertTrue(ExamArchive.objects.filter(title='Compilers').exists())


@override_settings(ROOT_URLCONF='core.urls.pulterit', ARCHIVE_ENABLED=False)
class PulteritExamBankArchiveRouteTests(TestCase):
    def setUp(self):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='pulterit-exam-user',
            password='pwd',
            membership_type=membership_type,
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_archive_exams_index_is_available_without_archive_app_routes(self):
        ExamArchive.objects.create(title='Geology')

        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Geology')


class ExamArchiveAdminFormTests(TestCase):
    def test_hide_for_gulis_is_editable(self):
        form = ExamArchiveAdminForm()

        self.assertIn('hide_for_gulis', form.fields)


class ExamArchiveAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='exam-admin',
            password='pwd',
            email='exam-admin@example.com',
        )
        self.client.force_login(self.admin_user)

    def test_pub_date_uses_flatpickr_datetime_widget(self):
        archive = ExamArchive.objects.create(title='Admin archive')

        response = self.client.get(reverse('admin:exambank_examarchive_change', args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'flatpickr-datetime')
        self.assertContains(response, 'core/js/flatpickr.min.js')
