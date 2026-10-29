import io
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.datastructures import MultiValueDict
from PIL import Image
from pypdf import PdfReader, PdfWriter

from members.models import Member

from .admin import ExpenseReceiptInline
from .forms import MAX_RECEIPTS, ExpenseClaimForm
from .models import MAX_RECEIPT_BYTES, ExpenseClaim, ExpenseReceipt
from .tasks import generate_expense_pdf
from .views import _enqueue_pdf_generation

IMAGE_FORMATS = {
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'png': 'PNG',
    'gif': 'GIF',
    'webp': 'WEBP',
}


def image_bytes(image_format='PNG', size=(10, 10)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'white').save(buffer, image_format)
    return buffer.getvalue()


def pdf_bytes():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(buffer)
    return buffer.getvalue()


def png_upload(name='kvitto.png'):
    return SimpleUploadedFile(name, image_bytes('PNG'), content_type='image/png')


def pdf_upload(name='kvitto.pdf'):
    return SimpleUploadedFile(name, pdf_bytes(), content_type='application/pdf')


def junk_upload(name='kvitto.jpg', content=b'inte en bild'):
    return SimpleUploadedFile(name, content, content_type='image/jpeg')


def claim_payload(**overrides):
    payload = {
        'recipient_name': 'Eva Testare',
        'description': 'Tågbiljett till styrelsemöte',
        'amount': '25.50',
        'payment_method': ExpenseClaim.PAYMENT_CASH,
        'bank_account': '',
    }
    payload.update(overrides)
    return payload


def claim_form(files=(), **overrides):
    return ExpenseClaimForm(data=claim_payload(**overrides), files=MultiValueDict({'receipts': list(files)}))


def make_member(username, **overrides):
    return Member.objects.create_user(username=username, password='pwd', email=f'{username}@example.com', **overrides)


def make_staff_member(username, permissions=()):
    group, _created = Group.objects.get_or_create(name=settings.STAFF_GROUPS[0])
    member = make_member(username)
    member.groups.add(group)
    for codename in permissions:
        member.user_permissions.add(Permission.objects.get(content_type__app_label='expenses', codename=codename))
    return member


def make_claim(member, **overrides):
    fields = {
        'recipient_name': 'Eva Testare',
        'description': 'Tågbiljett till styrelsemöte',
        'amount': Decimal('25.50'),
        'payment_method': ExpenseClaim.PAYMENT_CASH,
        'bank_account': '',
    }
    fields.update(overrides)
    return ExpenseClaim.objects.create(submitted_by=member, **fields)


def make_receipt(claim, name='kvitto.png', content=None):
    upload = SimpleUploadedFile(name, content if content is not None else image_bytes('PNG'))
    return ExpenseReceipt.objects.create(claim=claim, file=upload)


class TemporaryMediaMixin:
    """Give every test class its own MEDIA_ROOT so uploads never touch media/."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls._media_override.disable()
            shutil.rmtree(cls._media_root, ignore_errors=True)


class ExpenseUrlTests(SimpleTestCase):
    def test_list_url_is_mounted_under_expenses(self):
        self.assertEqual(reverse('expenses:list'), '/expenses/')


class ExpenseClaimHelperTests(SimpleTestCase):
    def test_get_absolute_url_points_at_the_claim_detail_page(self):
        self.assertEqual(ExpenseClaim(pk=7).get_absolute_url(), reverse('expenses:detail', args=[7]))

    def test_pdf_filename_uses_the_claim_pk(self):
        self.assertEqual(ExpenseClaim(pk=7).pdf_filename, 'kostnadsersattning-7.pdf')

    def test_is_reviewed_follows_the_status(self):
        expected = {
            ExpenseClaim.STATUS_PENDING: False,
            ExpenseClaim.STATUS_APPROVED: True,
            ExpenseClaim.STATUS_REJECTED: True,
        }
        for status, is_reviewed in expected.items():
            with self.subTest(status=status):
                self.assertEqual(ExpenseClaim(status=status).is_reviewed, is_reviewed)


class ExpenseClaimCleanTests(SimpleTestCase):
    """The IBAN rule lives in clean(), which both the site form and the admin
    change form run through model validation - see docs/dev/expenses.md."""

    @staticmethod
    def claim(**overrides):
        fields = {
            'recipient_name': 'Eva Testare',
            'description': 'Tågbiljett',
            'amount': Decimal('25.50'),
            'payment_method': ExpenseClaim.PAYMENT_CASH,
            'bank_account': '',
        }
        fields.update(overrides)
        return ExpenseClaim(**fields)

    def test_bank_claim_stores_the_formatted_iban(self):
        claim = self.claim(payment_method=ExpenseClaim.PAYMENT_BANK, bank_account='FI2112345600000785')

        claim.clean()

        self.assertEqual(claim.bank_account, 'FI21 1234 5600 0007 85')

    def test_bank_claim_requires_an_iban(self):
        claim = self.claim(payment_method=ExpenseClaim.PAYMENT_BANK, bank_account=' ')

        with self.assertRaises(ValidationError) as caught:
            claim.clean()

        self.assertIn('bank_account', caught.exception.message_dict)

    def test_bank_claim_rejects_an_invalid_iban(self):
        claim = self.claim(payment_method=ExpenseClaim.PAYMENT_BANK, bank_account='FI0012345600000785')

        with self.assertRaises(ValidationError) as caught:
            claim.clean()

        self.assertIn('bank_account', caught.exception.message_dict)

    def test_cash_claim_clears_the_bank_account(self):
        claim = self.claim(bank_account='FI2112345600000785')

        claim.clean()

        self.assertEqual(claim.bank_account, '')


class ExpenseClaimDatabaseRuleTests(TestCase):
    """The validators are backed by database constraints, so a write that skips
    clean() is still refused."""

    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('constraint-member')

    def test_full_clean_rejects_an_amount_below_one_cent(self):
        claim = ExpenseClaim(
            recipient_name='Eva Testare',
            description='Tågbiljett',
            amount=Decimal('0.00'),
            payment_method=ExpenseClaim.PAYMENT_CASH,
            submitted_by=self.member,
        )

        with self.assertRaises(ValidationError) as caught:
            claim.full_clean()

        self.assertIn('amount', caught.exception.message_dict)

    def test_amount_constraint_rejects_zero(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_claim(self.member, amount=Decimal('0.00'))

    def test_bank_account_constraint_rejects_a_blank_iban(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_claim(self.member, payment_method=ExpenseClaim.PAYMENT_BANK, bank_account='')


class ExpenseClaimRelationTests(TestCase):
    def test_deleting_the_submitter_deletes_their_claims(self):
        member = make_member('cascade-member')
        claim = make_claim(member)

        member.delete()

        self.assertFalse(ExpenseClaim.objects.filter(pk=claim.pk).exists())

    def test_deleting_the_reviewer_keeps_the_decision_and_the_claim(self):
        owner = make_member('reviewed-owner')
        reviewer = make_member('reviewed-reviewer')
        claim = make_claim(owner, status=ExpenseClaim.STATUS_APPROVED, reviewed_by=reviewer)

        reviewer.delete()

        claim.refresh_from_db()
        self.assertEqual(claim.status, ExpenseClaim.STATUS_APPROVED)
        self.assertIsNone(claim.reviewed_by)


class ExpenseReceiptStorageTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('storage-member')
        cls.claim = make_claim(cls.member)

    def test_receipt_is_stored_under_a_random_name_with_the_extension_kept(self):
        receipt = make_receipt(self.claim, name='Mitt Kvitto.JPG')

        path = Path(receipt.file.name)

        self.assertEqual(path.parent, Path(f'expenses/receipts/{timezone.localdate().year}'))
        self.assertEqual(path.suffix, '.jpg')
        self.assertRegex(path.stem, r'^[0-9a-f]{32}$')
        self.assertNotIn('kvitto', path.stem)

    def test_two_receipts_get_different_storage_names(self):
        first = make_receipt(self.claim, name='samma.png')
        second = make_receipt(self.claim, name='samma.png')

        self.assertNotEqual(first.file.name, second.file.name)

    def test_unknown_extension_is_dropped_from_the_storage_name(self):
        receipt = make_receipt(self.claim, name='anteckningar.txt', content=b'inte ett kvitto')

        path = Path(receipt.file.name)

        self.assertEqual(path.parent, Path(f'expenses/receipts/{timezone.localdate().year}'))
        self.assertEqual(path.suffix, '')
        self.assertRegex(path.name, r'^[0-9a-f]{32}$')

    def test_is_pdf_tracks_the_file_extension(self):
        pdf_receipt = make_receipt(self.claim, name='kvitto.pdf', content=pdf_bytes())
        image_receipt = make_receipt(self.claim, name='kvitto.png')

        self.assertTrue(pdf_receipt.is_pdf)
        self.assertFalse(image_receipt.is_pdf)

    def test_generated_pdf_is_stored_under_the_pdf_directory(self):
        claim = make_claim(self.member, recipient_name='PDF-mottagare')

        claim.pdf.save(f'kostnadsersattning-{claim.pk}.pdf', ContentFile(pdf_bytes()), save=True)

        path = Path(claim.pdf.name)
        self.assertEqual(path.parent, Path(f'expenses/pdfs/{timezone.localdate(claim.submitted_at).year}'))
        self.assertEqual(path.suffix, '.pdf')
        self.assertRegex(path.stem, r'^[0-9a-f]{32}$')

    def test_deleting_the_claim_deletes_the_stored_receipt_files(self):
        claim = make_claim(self.member, recipient_name='Raderas')
        receipt = make_receipt(claim)
        stored_path = Path(settings.MEDIA_ROOT, receipt.file.name)
        self.assertTrue(stored_path.exists())

        # django-cleanup deletes files after the transaction commits, which the
        # test transaction never does on its own.
        with self.captureOnCommitCallbacks(execute=True):
            claim.delete()

        self.assertFalse(stored_path.exists())
        self.assertFalse(ExpenseReceipt.objects.filter(pk=receipt.pk).exists())


class ExpenseClaimFormTests(TestCase):
    def test_accepts_every_allowed_image_extension_and_pdf(self):
        files = [
            SimpleUploadedFile(f'kvitto.{extension}', image_bytes(image_format), content_type='image/jpeg')
            for extension, image_format in IMAGE_FORMATS.items()
        ]
        files.append(pdf_upload())

        form = claim_form(files)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['receipts']), len(IMAGE_FORMATS) + 1)

    def test_rejects_an_unlisted_extension(self):
        form = claim_form([junk_upload('kvitto.txt', content=image_bytes('PNG'))])

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'unsupported')

    def test_rejects_a_jpg_that_is_not_an_image(self):
        form = claim_form([junk_upload('kvitto.jpg')])

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'invalid')

    def test_rejects_a_pdf_that_is_not_a_pdf(self):
        form = claim_form([junk_upload('kvitto.pdf', content=b'inte en pdf')])

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'invalid')

    def test_ignores_the_browser_supplied_content_type(self):
        upload = SimpleUploadedFile('kvitto.png', image_bytes('PNG'), content_type='application/octet-stream')

        form = claim_form([upload])

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_more_than_the_maximum_number_of_receipts(self):
        form = claim_form([png_upload(f'kvitto-{index}.png') for index in range(MAX_RECEIPTS + 1)])

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'too_many')

    def test_rejects_a_receipt_over_the_per_file_limit(self):
        upload = SimpleUploadedFile('stort.jpg', b'x' * (MAX_RECEIPT_BYTES + 1))

        form = claim_form([upload])

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'too_large')

    def test_rejects_receipts_over_the_total_limit(self):
        # Four 8 MB files are each under the per-file cap and together over the
        # 30 MB cap. Trailing zero bytes are ignored by Pillow's verify().
        padded_png = image_bytes('PNG') + b'\0' * (8 * 1024 * 1024)
        files = [SimpleUploadedFile(f'kvitto-{index}.png', padded_png) for index in range(4)]

        form = claim_form(files)

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'too_large_total')

    def test_requires_at_least_one_receipt(self):
        form = claim_form()

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['receipts'][0].code, 'required')

    def test_renders_a_multi_file_input(self):
        html = str(ExpenseClaimForm()['receipts'])

        self.assertIn('type="file"', html)
        self.assertIn('multiple', html)

    def test_bank_claim_without_an_iban_is_rejected_by_model_validation(self):
        form = claim_form([png_upload()], payment_method=ExpenseClaim.PAYMENT_BANK, bank_account='')

        self.assertFalse(form.is_valid())
        self.assertIn('bank_account', form.errors)
        self.assertIn('Bankkonto (IBAN) krävs för banköverföring.', form.errors['bank_account'])


class ExpenseClaimViewTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_member('owner-member', first_name='Eva', last_name='Testare')
        cls.other = make_member('other-member', first_name='Olle', last_name='Annan')
        cls.poster = make_member('poster-member', first_name='Poster', last_name='Testare')
        cls.staff = make_staff_member('expenses-treasurer', permissions=('view_expenseclaim', 'change_expenseclaim'))
        cls.claim = make_claim(cls.owner)
        cls.receipt = make_receipt(cls.claim)
        cls.other_claim = make_claim(cls.other, recipient_name='Olle Annan')
        cls.pdf_claim = make_claim(cls.owner, recipient_name='PDF Testare')
        cls.pdf_claim.pdf.save(f'kostnadsersattning-{cls.pdf_claim.pk}.pdf', ContentFile(pdf_bytes()), save=True)
        cls.no_pdf_claim = make_claim(cls.owner, recipient_name='Ingen PDF')

    def login(self, member):
        self.client.force_login(member, backend='members.backends.AuthBackend')

    def test_anonymous_visitors_are_redirected_to_the_login_page(self):
        urls = (
            reverse('expenses:list'),
            reverse('expenses:create'),
            reverse('expenses:detail', args=[self.claim.pk]),
            reverse('expenses:receipt', args=[self.receipt.pk]),
            reverse('expenses:pdf', args=[self.pdf_claim.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    f'{reverse("members:login")}?next={quote(url, safe="")}',
                    fetch_redirect_response=False,
                )

    def test_member_list_shows_only_their_own_claims(self):
        self.login(self.owner)

        response = self.client.get(reverse('expenses:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eva Testare')
        self.assertNotContains(response, 'Olle Annan')

    def test_staff_list_shows_every_claim(self):
        self.login(self.staff)

        response = self.client.get(reverse('expenses:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eva Testare')
        self.assertContains(response, 'Olle Annan')

    def test_owner_can_read_the_claim_detail_page(self):
        self.login(self.owner)

        response = self.client.get(reverse('expenses:detail', args=[self.claim.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eva Testare')
        # Rendered through the Swedish locale, so the decimal separator is a comma.
        self.assertContains(response, '25,50 EUR')

    def test_staff_can_read_any_claim_detail_page(self):
        self.login(self.staff)

        response = self.client.get(reverse('expenses:detail', args=[self.other_claim.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Olle Annan')

    def test_another_member_gets_a_404_for_someone_elses_claim(self):
        self.login(self.other)

        response = self.client.get(reverse('expenses:detail', args=[self.claim.pk]))

        self.assertEqual(response.status_code, 404)

    def test_owner_can_stream_their_receipt_file(self):
        self.login(self.owner)

        response = self.client.get(reverse('expenses:receipt', args=[self.receipt.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(b''.join(response.streaming_content), image_bytes('PNG'))

    def test_staff_can_stream_any_receipt_file(self):
        self.login(self.staff)

        response = self.client.get(reverse('expenses:receipt', args=[self.receipt.pk]))

        self.assertEqual(response.status_code, 200)

    def test_another_member_gets_a_404_for_someone_elses_receipt(self):
        self.login(self.other)

        response = self.client.get(reverse('expenses:receipt', args=[self.receipt.pk]))

        self.assertEqual(response.status_code, 404)

    def test_receipt_file_missing_from_storage_is_a_404(self):
        self.login(self.owner)
        claim = make_claim(self.owner, recipient_name='Saknat kvitto')
        receipt = make_receipt(claim)
        receipt.file.storage.delete(receipt.file.name)

        response = self.client.get(reverse('expenses:receipt', args=[receipt.pk]))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_download_the_generated_pdf_as_an_attachment(self):
        self.login(self.staff)

        response = self.client.get(reverse('expenses:pdf', args=[self.pdf_claim.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(f'kostnadsersattning-{self.pdf_claim.pk}.pdf', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_members_cannot_download_the_generated_pdf(self):
        self.login(self.owner)

        response = self.client.get(reverse('expenses:pdf', args=[self.pdf_claim.pk]))

        self.assertEqual(response.status_code, 404)

    def test_pdf_download_is_a_404_before_the_pdf_is_generated(self):
        self.login(self.staff)

        response = self.client.get(reverse('expenses:pdf', args=[self.no_pdf_claim.pk]))

        self.assertEqual(response.status_code, 404)

    def test_pdf_download_is_a_404_when_the_stored_file_is_missing(self):
        self.login(self.staff)
        claim = make_claim(self.owner, recipient_name='Försvunnen PDF')
        claim.pdf.save(f'kostnadsersattning-{claim.pk}.pdf', ContentFile(pdf_bytes()), save=True)
        claim.pdf.storage.delete(claim.pdf.name)

        response = self.client.get(reverse('expenses:pdf', args=[claim.pk]))

        self.assertEqual(response.status_code, 404)

    def test_create_page_prefills_the_recipient_with_the_members_full_name(self):
        self.login(self.poster)

        response = self.client.get(reverse('expenses:create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Poster Testare"')

    def test_valid_submission_creates_claim_and_receipts_and_queues_the_pdf(self):
        self.login(self.poster)
        files = [png_upload('bild.png'), pdf_upload('bilaga.pdf')]

        # The task is queued on commit so the worker cannot read a claim whose
        # receipts are still uncommitted; the test transaction only commits
        # when the captured callbacks are executed.
        with patch('expenses.views.generate_expense_pdf.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('expenses:create'), claim_payload(receipts=files))

        claim = ExpenseClaim.objects.get(submitted_by=self.poster)
        self.assertRedirects(response, reverse('expenses:detail', args=[claim.pk]))
        self.assertEqual(claim.recipient_name, 'Eva Testare')
        self.assertEqual(claim.amount, Decimal('25.50'))
        self.assertEqual(claim.receipts.count(), 2)
        for receipt in claim.receipts.all():
            self.assertTrue(receipt.file.storage.exists(receipt.file.name))
        delay.assert_called_once_with(claim.pk)

    def test_valid_submission_redirects_with_a_success_message(self):
        self.login(self.poster)

        with patch('expenses.views.generate_expense_pdf.delay'):
            response = self.client.post(reverse('expenses:create'), claim_payload(receipts=[png_upload()]), follow=True)

        claim = ExpenseClaim.objects.get(submitted_by=self.poster)
        self.assertRedirects(response, reverse('expenses:detail', args=[claim.pk]))
        self.assertContains(response, 'Kostnadsersättningen har skickats in.')

    def test_invalid_submission_renders_errors_and_creates_nothing(self):
        self.login(self.poster)

        with patch('expenses.views.generate_expense_pdf.delay') as delay:
            response = self.client.post(reverse('expenses:create'), claim_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ExpenseClaim.objects.filter(submitted_by=self.poster).count(), 0)
        self.assertEqual(ExpenseReceipt.objects.count(), 1)  # Only the receipt from setUpTestData.
        self.assertContains(response, 'Detta fält måste fyllas i.')
        delay.assert_not_called()

    def test_bank_submission_stores_the_formatted_iban(self):
        self.login(self.poster)

        with patch('expenses.views.generate_expense_pdf.delay'):
            self.client.post(
                reverse('expenses:create'),
                claim_payload(
                    payment_method=ExpenseClaim.PAYMENT_BANK,
                    bank_account='FI2112345600000785',
                    receipts=[png_upload()],
                ),
            )

        claim = ExpenseClaim.objects.get(submitted_by=self.poster)
        self.assertEqual(claim.bank_account, 'FI21 1234 5600 0007 85')

    def test_detail_page_renders_english_catalog_strings(self):
        # The language cookie is what date.middleware.LangMiddleware reads; the
        # translation override alone does not survive a real request.
        self.login(self.owner)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'

        with translation.override('en'):
            response = self.client.get(reverse('expenses:detail', args=[self.claim.pk]))

        self.assertContains(response, 'Expense claim')
        self.assertNotContains(response, 'Kostnadsersättning')


class GenerateExpensePdfTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('pdf-member', first_name='Eva', last_name='Testare')
        cls.claim = make_claim(cls.member, description='Taxi och tåg')
        make_receipt(cls.claim, name='bild.png')
        make_receipt(cls.claim, name='bilaga.pdf', content=pdf_bytes())

    def read_pdf(self, claim):
        with claim.pdf.storage.open(claim.pdf.name, 'rb') as handle:
            return handle.read()

    def test_generates_a_pdf_with_claim_image_and_appended_receipt_pages(self):
        generate_expense_pdf(self.claim.pk)

        self.claim.refresh_from_db()
        data = self.read_pdf(self.claim)
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertGreaterEqual(len(PdfReader(io.BytesIO(data)).pages), 3)
        self.assertIsNotNone(self.claim.pdf_generated_at)

    def test_claim_page_carries_the_claim_details_and_bank_account(self):
        claim = make_claim(
            self.member,
            recipient_name='Eva Testare',
            description='Taxi',
            payment_method=ExpenseClaim.PAYMENT_BANK,
            bank_account='FI21 1234 5600 0007 85',
        )
        make_receipt(claim, name='bild.png')

        generate_expense_pdf(claim.pk)

        claim.refresh_from_db()
        text = PdfReader(io.BytesIO(self.read_pdf(claim))).pages[0].extract_text()
        self.assertIn('Eva Testare', text)
        self.assertIn('25.50 EUR', text)
        self.assertIn('FI21 1234 5600 0007 85', text)

    def test_pdf_is_stored_under_a_random_name_in_the_pdf_directory(self):
        generate_expense_pdf(self.claim.pk)

        self.claim.refresh_from_db()
        path = Path(self.claim.pdf.name)
        self.assertEqual(path.parent, Path(f'expenses/pdfs/{timezone.localdate(self.claim.submitted_at).year}'))
        self.assertEqual(path.suffix, '.pdf')
        self.assertRegex(path.stem, r'^[0-9a-f]{32}$')

    def test_regenerating_replaces_the_old_stored_pdf(self):
        claim = make_claim(self.member, recipient_name='Ny PDF')
        make_receipt(claim, name='bild.png')
        generate_expense_pdf(claim.pk)
        claim.refresh_from_db()
        old_name = claim.pdf.name

        generate_expense_pdf(claim.pk)

        claim.refresh_from_db()
        self.assertNotEqual(claim.pdf.name, old_name)
        self.assertFalse(claim.pdf.storage.exists(old_name))
        self.assertTrue(claim.pdf.storage.exists(claim.pdf.name))
        self.assertTrue(self.read_pdf(claim).startswith(b'%PDF-'))

    def test_missing_claim_is_a_no_op(self):
        with self.assertLogs('date', level='WARNING') as logs:
            self.assertIsNone(generate_expense_pdf(10_000_000))

        self.assertTrue(any('10000000' in line for line in logs.output))


class ExpenseClaimAdminTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = make_staff_member('expenses-admin', permissions=('view_expenseclaim', 'change_expenseclaim'))
        cls.member = make_member('admin-claim-owner')
        cls.claim = make_claim(cls.member)
        cls.other_claim = make_claim(cls.member, recipient_name='Andra utlägget')
        cls.receipt = make_receipt(cls.claim)

    def setUp(self):
        self.client.force_login(self.staff, backend='members.backends.AuthBackend')

    def post_action(self, action, claims):
        return self.client.post(
            reverse('admin:expenses_expenseclaim_changelist'),
            {
                'action': action,
                '_selected_action': [str(claim.pk) for claim in claims],
                'index': '0',
            },
        )

    def test_admin_refuses_to_add_a_claim(self):
        response = self.client.get(reverse('admin:expenses_expenseclaim_add'))

        self.assertEqual(response.status_code, 403)

    def test_staff_can_read_the_changelist(self):
        response = self.client.get(reverse('admin:expenses_expenseclaim_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eva Testare')
        self.assertContains(response, 'Andra utlägget')

    def test_mark_approved_updates_only_the_selected_rows(self):
        response = self.post_action('mark_approved', [self.claim])

        self.assertEqual(response.status_code, 302)
        self.claim.refresh_from_db()
        self.other_claim.refresh_from_db()
        self.assertEqual(self.claim.status, ExpenseClaim.STATUS_APPROVED)
        self.assertEqual(self.claim.reviewed_by, self.staff)
        self.assertEqual(self.claim.reviewed_at, timezone.localdate())
        self.assertEqual(self.other_claim.status, ExpenseClaim.STATUS_PENDING)
        self.assertIsNone(self.other_claim.reviewed_by)

    def test_mark_rejected_updates_only_the_selected_rows(self):
        response = self.post_action('mark_rejected', [self.other_claim])

        self.assertEqual(response.status_code, 302)
        self.claim.refresh_from_db()
        self.other_claim.refresh_from_db()
        self.assertEqual(self.other_claim.status, ExpenseClaim.STATUS_REJECTED)
        self.assertEqual(self.other_claim.reviewed_by, self.staff)
        self.assertEqual(self.other_claim.reviewed_at, timezone.localdate())
        self.assertEqual(self.claim.status, ExpenseClaim.STATUS_PENDING)

    @patch('expenses.admin.generate_expense_pdf.delay')
    def test_regenerate_pdf_queues_one_task_per_selected_claim(self, delay):
        response = self.post_action('regenerate_pdf', [self.claim, self.other_claim])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(delay.call_count, 2)
        self.assertEqual({call.args[0] for call in delay.call_args_list}, {self.claim.pk, self.other_claim.pk})

    def test_inline_receipt_link_points_at_the_authenticated_receipt_view(self):
        inline = ExpenseReceiptInline(ExpenseClaim, admin.site)

        html = inline.receipt_link(self.receipt)

        self.assertIn(reverse('expenses:receipt', args=[self.receipt.pk]), html)

    def test_inline_refuses_adds_and_deletes(self):
        inline = ExpenseReceiptInline(ExpenseClaim, admin.site)
        request = RequestFactory().get('/')
        request.user = self.staff

        self.assertFalse(inline.has_add_permission(request))
        self.assertFalse(inline.has_delete_permission(request))

    def test_actions_do_not_overwrite_an_existing_decision(self):
        self.claim.status = ExpenseClaim.STATUS_REJECTED
        self.claim.save(update_fields=['status'])

        self.post_action('mark_approved', [self.claim])

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ExpenseClaim.STATUS_REJECTED)


class ReceiptSafetyLimitTests(TemporaryMediaMixin, TestCase):
    """Inputs that would expand into a large decode are refused by the form."""

    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('limits-member')

    def assert_receipts_rejected(self, form, message_fragment):
        self.assertFalse(form.is_valid())
        self.assertIn('receipts', form.errors)
        self.assertIn(message_fragment, form.errors['receipts'][0])

    def test_image_above_the_pixel_cap_is_rejected(self):
        with patch('expenses.forms.MAX_IMAGE_PIXELS', 50):
            form = claim_form(files=[png_upload()])
            self.assert_receipts_rejected(form, 'för många pixlar')

    def test_pdf_above_the_page_cap_is_rejected(self):
        with patch('expenses.forms.MAX_PDF_PAGES', 0):
            form = claim_form(files=[pdf_upload()])
            self.assert_receipts_rejected(form, 'för många sidor')

    def test_image_content_with_a_disallowed_format_is_rejected(self):
        buffer = io.BytesIO()
        Image.new('RGB', (10, 10), 'white').save(buffer, 'BMP')
        upload = SimpleUploadedFile('kvitto.jpg', buffer.getvalue())

        form = claim_form(files=[upload])

        self.assert_receipts_rejected(form, 'giltig bild')

    def test_decompression_bomb_error_is_a_validation_error(self):
        with patch('expenses.forms.Image.open', side_effect=Image.DecompressionBombError('bomb')):
            form = claim_form(files=[png_upload()])
            self.assert_receipts_rejected(form, 'giltig bild')


class ExpenseListPaginationTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('pagination-member')
        for _ in range(51):
            make_claim(cls.member)

    def test_claims_are_paginated_fifty_per_page(self):
        self.client.force_login(self.member)

        first = self.client.get(reverse('expenses:list'))
        second = self.client.get(reverse('expenses:list'), {'page': 2})

        self.assertEqual(len(first.context['claims']), 50)
        self.assertContains(first, '?page=2')
        self.assertEqual(len(second.context['claims']), 1)
        self.assertContains(second, '2 / 2')


class EnqueueFailureTests(SimpleTestCase):
    def test_broker_failure_is_logged_and_swallowed(self):
        with patch('expenses.views.generate_expense_pdf.delay', side_effect=RuntimeError('broker down')) as delay:
            with self.assertLogs('date', level='ERROR') as logs:
                _enqueue_pdf_generation(7)

        delay.assert_called_once_with(7)
        self.assertTrue(any('7' in line for line in logs.output))


class PdfRobustnessTests(TemporaryMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_member('pdf-robustness-member')

    def read_pdf(self, claim):
        with claim.pdf.storage.open(claim.pdf.name, 'rb') as handle:
            return handle.read()

    def test_unreadable_image_receipt_does_not_abort_the_pdf(self):
        claim = make_claim(self.member)
        make_receipt(claim, name='trasig.jpg', content=b'inte en bild')
        make_receipt(claim, name='bild.png')

        with self.assertLogs('date', level='ERROR'):
            generate_expense_pdf(claim.pk)

        claim.refresh_from_db()
        self.assertTrue(self.read_pdf(claim).startswith(b'%PDF-'))

    def test_long_description_continues_on_new_pages(self):
        claim = make_claim(self.member, description='Ord ' * 2000)
        make_receipt(claim, name='bild.png')

        generate_expense_pdf(claim.pk)

        claim.refresh_from_db()
        reader = PdfReader(io.BytesIO(self.read_pdf(claim)))
        self.assertGreaterEqual(len(reader.pages), 3)

    def test_unicode_outside_latin1_is_replaced_instead_of_crashing(self):
        claim = make_claim(self.member, recipient_name='Yamada 太郎', description='東京の交通費')

        generate_expense_pdf(claim.pk)

        claim.refresh_from_db()
        self.assertTrue(self.read_pdf(claim).startswith(b'%PDF-'))
