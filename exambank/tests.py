import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from exambank.admin import ExamFileInline
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

    def test_direct_upload_skips_files_that_fail_finalize_with_warning(self):
        archive = ExamArchive.objects.create(
            title='Networks',
            pub_date=timezone.datetime(2024, 1, 1, tzinfo=timezone.UTC),
        )
        good = {'key': 'tmp/' + 'a' * 32 + '.pdf', 'name': 'good.pdf', 'size': 10}
        bad = {'key': 'tmp/' + 'b' * 32 + '.pdf', 'name': 'bad.pdf', 'size': 10}
        payload = json.dumps([good, bad])

        def fake_finalize(temp_key, instance, field, filename, expected_size=None):
            if temp_key == bad['key']:
                raise ValueError('boom')
            instance.document.name = f'2024/networks/{filename}'
            instance.save()
            return f'2024/networks/{filename}'

        with self.settings(USE_S3=True, DIRECT_UPLOADS_ENABLED=True):
            with patch('core.uploads.finalize_upload', side_effect=fake_finalize):
                response = self.client.post(
                    reverse('archive:exam_upload', args=[archive.pk]),
                    {'title': 'tent 02.02.2024', 'exam': payload},
                    follow=True,
                )

        self.assertRedirects(response, reverse('archive:exams_detail', args=[archive.pk]))
        files = list(ExamFile.objects.filter(archive=archive).order_by('title'))
        self.assertEqual([f.title for f in files], ['tent 02.02.2024'])
        self.assertEqual(files[0].document.name, '2024/networks/good.pdf')

        warnings = [m.message for m in response.context['messages']]
        self.assertTrue(any('bad.pdf' in message for message in warnings))

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


class ExamBankAccessTests(TestCase):
    def test_default_access_requires_member_sign_in(self):
        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/members/login/', response['Location'])

    def test_password_access_allows_anonymous_exam_bank_routes(self):
        archive = ExamArchive.objects.create(title='Geology')
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('stone')
        access_settings.save()

        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tentarkiv')

        response = self.client.post(reverse('archive:exams'), {'password': 'wrong'})

        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('archive:exams'), {'password': 'stone'})

        self.assertRedirects(response, reverse('archive:exams'))

        response = self.client.get(reverse('archive:exams_detail', args=[archive.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Geology')

        response = self.client.get(reverse('archive:exam_upload', args=[archive.pk]))

        self.assertEqual(response.status_code, 200)

    def test_password_access_redirects_to_exam_index_from_detail_route(self):
        archive = ExamArchive.objects.create(title='Geology')
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('stone')
        access_settings.save()

        response = self.client.post(reverse('archive:exams_detail', args=[archive.pk]), {'password': 'stone'})

        self.assertRedirects(response, reverse('archive:exams'))

    def test_passwordless_public_access_allows_anonymous_exam_bank(self):
        ExamArchive.objects.create(title='Open archive')
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('')
        access_settings.save()

        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open archive')

    def test_repeated_wrong_passwords_trigger_lockout(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('stone')
        access_settings.save()

        for _ in range(5):
            response = self.client.post(reverse('archive:exams'), {'password': 'wrong'})

        self.assertEqual(response.status_code, 429)

        response = self.client.post(reverse('archive:exams'), {'password': 'stone'})

        self.assertEqual(response.status_code, 429)

    def test_password_change_invalidates_existing_session_access(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('stone')
        access_settings.save()

        self.client.post(reverse('archive:exams'), {'password': 'stone'})

        access_settings.set_password('granite')
        access_settings.save()

        response = self.client.get(reverse('archive:exams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lösenord')


@override_settings(ARCHIVE_ACCESS_REQUIRES_ELIGIBILITY=True)
class SFExamBankAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        cls.member = Member.objects.create_user(
            username='sf-exam-member', password='pwd', membership_type=membership_type
        )
        cls.archive = ExamArchive.objects.create(title='SF exams')

    def setUp(self):
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_ineligible_member_cannot_read_exam_index_or_detail(self):
        for url in (
            reverse('archive:exams'),
            reverse('archive:exams_detail', args=[self.archive.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_eligible_member_can_read_exam_index_and_detail(self):
        self.member.archive_access_eligible = True
        self.member.save(update_fields=['archive_access_eligible'])
        for url in (
            reverse('archive:exams'),
            reverse('archive:exams_detail', args=[self.archive.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_shared_password_does_not_bypass_sf_member_eligibility(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.require_sign_in = False
        access_settings.set_password('stone')
        access_settings.save()

        response = self.client.post(reverse('archive:exams'), {'password': 'stone'})

        self.assertEqual(response.status_code, 302)
        self.assertIn('/members/login/', response['Location'])


class ExamArchiveAdminFormTests(TestCase):
    def test_hide_for_gulis_is_editable(self):
        form = ExamArchiveAdminForm()

        self.assertIn('hide_for_gulis', form.fields)

    def test_multi_upload_is_deferred_until_archive_is_saved(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            form = ExamArchiveAdminForm(
                data={'title': 'Admin uploads', 'pub_date': '2026-08-24 12:00:00'},
                files=MultiValueDict({'files': [SimpleUploadedFile('exam.pdf', b'%PDF-1.4')]}),
            )

            self.assertTrue(form.is_valid(), form.errors)
            archive = form.save(commit=False)
            self.assertIsNone(archive.pk)
            self.assertEqual(ExamFile.objects.count(), 0)

            archive.save()
            form.save_m2m()

            self.assertTrue(ExamFile.objects.filter(archive=archive, document__endswith='exam.pdf').exists())

    def test_legacy_collection_permission_applies_to_file_inline(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                has_perm=Mock(
                    side_effect=lambda perm: (
                        perm
                        in {
                            'archive.view_document',
                            'archive.add_document',
                            'archive.change_document',
                            'archive.delete_document',
                        }
                    )
                )
            )
        )
        inline = ExamFileInline(ExamArchive, admin.site)

        self.assertTrue(inline.has_view_permission(request))
        self.assertTrue(inline.has_add_permission(request))
        self.assertTrue(inline.has_change_permission(request))
        self.assertTrue(inline.has_delete_permission(request))


class ExamBankAccessSettingsAdminFormTests(TestCase):
    def test_password_is_hashed_when_saved(self):
        form = ExamBankAccessSettingsAdminForm(
            {
                'require_sign_in': '',
                'password': 'granite',
            }
        )

        self.assertTrue(form.is_valid())
        access_settings = form.save()

        self.assertFalse(access_settings.require_sign_in)
        self.assertNotEqual(access_settings.password_hash, 'granite')
        self.assertTrue(access_settings.check_password('granite'))

    def test_password_placeholder_keeps_existing_hash(self):
        access_settings = ExamBankAccessSettings.get_solo()
        access_settings.set_password('granite')
        access_settings.save()
        original_hash = access_settings.password_hash

        form = ExamBankAccessSettingsAdminForm(
            {
                'require_sign_in': 'on',
                'password': ExamBankAccessSettingsAdminForm.PASSWORD_PLACEHOLDER,
            },
            instance=access_settings,
        )

        self.assertTrue(form.is_valid())
        access_settings = form.save()

        self.assertEqual(access_settings.password_hash, original_hash)


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

    def test_admin_add_with_multi_upload_creates_archive_and_file(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse('admin:exambank_examarchive_add'),
                {
                    'title': 'Admin upload archive',
                    'pub_date': '2026-08-24 12:00',
                    'files': SimpleUploadedFile('admin-exam.pdf', b'%PDF-1.4'),
                    'examfile_set-TOTAL_FORMS': '0',
                    'examfile_set-INITIAL_FORMS': '0',
                    'examfile_set-MIN_NUM_FORMS': '0',
                    'examfile_set-MAX_NUM_FORMS': '1000',
                    '_save': 'Save',
                },
            )

            self.assertEqual(response.status_code, 302)
            archive = ExamArchive.objects.get(title='Admin upload archive')
            self.assertTrue(ExamFile.objects.filter(archive=archive, document__endswith='admin-exam.pdf').exists())

    def test_changelist_links_to_access_settings(self):
        access_settings = ExamBankAccessSettings.get_solo()

        response = self.client.get(reverse('admin:exambank_examarchive_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Åtkomstinställningar')
        self.assertContains(response, reverse('admin:exambank_examarchive_access_settings'))

        response = self.client.get(reverse('admin:exambank_examarchive_access_settings'))

        self.assertRedirects(
            response,
            reverse('admin:exambank_exambankaccesssettings_change', args=[access_settings.pk]),
        )

    def test_access_settings_redirect_requires_settings_permission(self):
        staff_group = Group.objects.create(name='admin')
        staff_user = get_user_model().objects.create_user(
            username='exam-staff-no-set',
            password='pwd',
            email='exam-staff-no-set@example.com',
        )
        staff_user.groups.add(staff_group)
        self.client.force_login(staff_user)

        response = self.client.get(reverse('admin:exambank_examarchive_access_settings'))

        self.assertEqual(response.status_code, 403)

    def test_access_settings_is_hidden_from_app_index(self):
        response = self.client.get('/admin/exambank/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tentarkiv')
        self.assertNotContains(response, 'Åtkomst till tentarkiv')


class ExamBankAppIndexLegacyPermissionTests(TestCase):
    def test_app_index_works_with_legacy_archive_permission(self):
        from django.conf import settings
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        staff_group, _ = Group.objects.get_or_create(name=settings.STAFF_GROUPS[0])
        member = Member.objects.create_user(
            username='legacy-staff',
            password='pwd',
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        member.groups.add(staff_group)

        content_type, _ = ContentType.objects.get_or_create(
            app_label='archive',
            model='examcollection',
        )
        legacy_view, _ = Permission.objects.get_or_create(
            codename='view_examcollection',
            content_type=content_type,
            defaults={'name': 'Can view exam collection'},
        )
        member.user_permissions.add(legacy_view)

        self.client.force_login(member, backend='members.backends.AuthBackend')

        response = self.client.get('/admin/exambank/')

        self.assertEqual(response.status_code, 200)


@override_settings(USE_S3=True, DIRECT_UPLOADS_ENABLED=True)
class DirectUploadTests(TestCase):
    def setUp(self):
        from members.models import ORDINARY_MEMBER, MembershipType

        membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.member = Member.objects.create_user(
            username='exam-uploader',
            password='pwd',
            membership_type=membership_type,
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        self.archive = ExamArchive.objects.create(title='Math 1')
        ExamBankAccessSettings.objects.create(require_sign_in=False)

    def test_public_direct_upload_uses_form_title(self):
        import json
        from unittest.mock import patch

        payload = json.dumps([{'key': 'tmp/' + 'c' * 32 + '.pdf', 'name': 'tent.pdf', 'size': 123}])
        with patch('core.uploads.finalize_upload', return_value='2026/math-1/tent.pdf') as finalize:
            response = self.client.post(
                reverse('archive:exam_upload', args=[self.archive.pk]),
                {'title': 'Tent 23.08.2026', 'exam': payload},
            )

        self.assertRedirects(response, reverse('archive:exams_detail', args=[self.archive.pk]))
        exam_file = ExamFile.objects.get()
        self.assertEqual(exam_file.title, 'Tent 23.08.2026')
        self.assertEqual(exam_file.document.name, '2026/math-1/tent.pdf')
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args[1]['expected_size'], 123)
