import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from exambank.forms import ExamArchiveAdminForm, ExamBankAccessSettingsAdminForm
from exambank.models import ExamArchive, ExamBankAccessSettings, ExamFile
from members.models import ORDINARY_MEMBER, Member, MembershipType


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
            username="exam-user",
            password="pwd",
            membership_type=membership_type,
        )
        self.client.force_login(self.member, backend="members.backends.AuthBackend")

    def test_legacy_archive_exams_index_renders_archives(self):
        ExamArchive.objects.create(title="Algorithms")

        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Algorithms")

    def test_legacy_archive_exams_detail_renders_exam_files(self):
        archive = ExamArchive.objects.create(title="Databases")
        ExamFile.objects.create(
            archive=archive,
            title="tent 01.01.2024",
            document=SimpleUploadedFile("database.pdf", b"pdf"),
        )

        response = self.client.get(reverse("archive:exams_detail", args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Databases")
        self.assertContains(response, "tent 01.01.2024")

    def test_legacy_archive_exam_upload_adds_files(self):
        archive = ExamArchive.objects.create(
            title="Networks",
            pub_date=timezone.datetime(2024, 1, 1, tzinfo=timezone.UTC),
        )

        response = self.client.post(
            reverse("archive:exam_upload", args=[archive.pk]),
            {
                "title": "tent 02.02.2024",
                "exam": SimpleUploadedFile("networks.pdf", b"pdf"),
            },
        )

        self.assertRedirects(response, reverse("archive:exams_detail", args=[archive.pk]))
        exam_file = ExamFile.objects.get(archive=archive)
        self.assertEqual(exam_file.title, "tent 02.02.2024")
        self.assertEqual(exam_file.document.name, "2024/networks/networks.pdf")

    def test_legacy_archive_exam_archive_upload_adds_archive(self):
        response = self.client.post(
            reverse("archive:exam_archive_upload"),
            {"title": "Compilers"},
        )

        self.assertRedirects(response, reverse("archive:exams"))
        self.assertTrue(ExamArchive.objects.filter(title="Compilers").exists())


@override_settings(ROOT_URLCONF="core.urls.pulterit", ARCHIVE_ENABLED=False)
class PulteritExamBankArchiveRouteTests(TestCase):
    def setUp(self):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username="pulterit-exam-user",
            password="pwd",
            membership_type=membership_type,
        )
        self.client.force_login(self.member, backend="members.backends.AuthBackend")

    def test_archive_exams_index_is_available_without_archive_app_routes(self):
        ExamArchive.objects.create(title="Geology")

        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Geology")


class ExamBankAccessTests(TestCase):
    def test_default_access_requires_member_sign_in(self):
        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/members/login/", response["Location"])

    def test_password_access_allows_anonymous_exam_bank_routes(self):
        archive = ExamArchive.objects.create(title="Geology")
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password("stone")
        access_settings.save()

        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tentarkiv")

        response = self.client.post(reverse("archive:exams"), {"password": "wrong"})

        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse("archive:exams"), {"password": "stone"})

        self.assertRedirects(response, reverse("archive:exams"))

        response = self.client.get(reverse("archive:exams_detail", args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Geology")

        response = self.client.get(reverse("archive:exam_upload", args=[archive.pk]))

        self.assertEqual(response.status_code, 200)

    def test_password_access_redirects_to_exam_index_from_detail_route(self):
        archive = ExamArchive.objects.create(title="Geology")
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password("stone")
        access_settings.save()

        response = self.client.post(reverse("archive:exams_detail", args=[archive.pk]), {"password": "stone"})

        self.assertRedirects(response, reverse("archive:exams"))

    def test_passwordless_public_access_allows_anonymous_exam_bank(self):
        ExamArchive.objects.create(title="Open archive")
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password("")
        access_settings.save()

        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open archive")

    def test_repeated_wrong_passwords_trigger_lockout(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password("stone")
        access_settings.save()

        for _ in range(5):
            response = self.client.post(reverse("archive:exams"), {"password": "wrong"})

        self.assertEqual(response.status_code, 429)

        response = self.client.post(reverse("archive:exams"), {"password": "stone"})

        self.assertEqual(response.status_code, 429)

    def test_password_change_invalidates_existing_session_access(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password("stone")
        access_settings.save()

        self.client.post(reverse("archive:exams"), {"password": "stone"})

        access_settings.set_password("granite")
        access_settings.save()

        response = self.client.get(reverse("archive:exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lösenord")


class ExamArchiveAdminFormTests(TestCase):
    def test_hide_for_gulis_is_editable(self):
        form = ExamArchiveAdminForm()

        self.assertIn("hide_for_gulis", form.fields)


class ExamBankAccessSettingsAdminFormTests(TestCase):
    def test_password_is_hashed_when_saved(self):
        form = ExamBankAccessSettingsAdminForm(
            {
                "require_sign_in": "",
                "password": "granite",
            }
        )

        self.assertTrue(form.is_valid())
        access_settings = form.save()

        self.assertFalse(access_settings.require_sign_in)
        self.assertNotEqual(access_settings.password_hash, "granite")
        self.assertTrue(access_settings.check_password("granite"))

    def test_password_placeholder_keeps_existing_hash(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.set_password("granite")
        access_settings.save()
        original_hash = access_settings.password_hash

        form = ExamBankAccessSettingsAdminForm(
            {
                "require_sign_in": "on",
                "password": ExamBankAccessSettingsAdminForm.PASSWORD_PLACEHOLDER,
            },
            instance=access_settings,
        )

        self.assertTrue(form.is_valid())
        access_settings = form.save()

        self.assertEqual(access_settings.password_hash, original_hash)


class ExamArchiveAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="exam-admin",
            password="pwd",
            email="exam-admin@example.com",
        )
        self.client.force_login(self.admin_user)

    def test_pub_date_uses_flatpickr_datetime_widget(self):
        archive = ExamArchive.objects.create(title="Admin archive")

        response = self.client.get(reverse("admin:exambank_examarchive_change", args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "flatpickr-datetime")
        self.assertContains(response, "core/js/flatpickr.min.js")


class ExamBankAppIndexLegacyPermissionTests(TestCase):
    def test_app_index_works_with_legacy_archive_permission(self):
        from django.conf import settings
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        staff_group, _ = Group.objects.get_or_create(name=settings.STAFF_GROUPS[0])
        member = Member.objects.create_user(
            username="legacy-staff",
            password="pwd",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        member.groups.add(staff_group)

        content_type, _ = ContentType.objects.get_or_create(
            app_label="archive",
            model="examcollection",
        )
        legacy_view, _ = Permission.objects.get_or_create(
            codename="view_examcollection",
            content_type=content_type,
            defaults={"name": "Can view exam collection"},
        )
        member.user_permissions.add(legacy_view)

        self.client.force_login(member, backend="members.backends.AuthBackend")

        response = self.client.get("/admin/exambank/")

        self.assertEqual(response.status_code, 200)
