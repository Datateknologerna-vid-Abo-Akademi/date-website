from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from publications.models import PDFFile


class PDFFileAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="publication-admin",
            password="pwd",
            email="publication-admin@example.com",
        )
        self.client.force_login(self.admin_user)

    def test_change_page_renders_when_file_url_cannot_be_resolved(self):
        timestamp = timezone.now()
        PDFFile.objects.bulk_create([
            PDFFile(
                title="Broken PDF",
                slug="broken-pdf",
                file="pdfs/broken.pdf",
                uploaded_at=timestamp,
                updated_at=timestamp,
            )
        ])
        pdf_file = PDFFile.objects.get(slug="broken-pdf")

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken storage"),
        ):
            response = self.client.get(reverse("admin:publications_pdffile_change", args=[pdf_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pdfs/broken.pdf")


class PDFFileListTests(TestCase):
    def test_list_renders_when_file_url_cannot_be_resolved(self):
        timestamp = timezone.now()
        PDFFile.objects.bulk_create([
            PDFFile(
                title="Broken PDF",
                slug="broken-pdf",
                file="pdfs/broken.pdf",
                uploaded_at=timestamp,
                updated_at=timestamp,
            )
        ])

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken storage"),
        ):
            response = self.client.get(reverse("publications:pdf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Broken PDF")
        self.assertNotContains(response, "data-pdf-url")

    def test_list_links_redirect_publication_to_external_url(self):
        PDFFile.objects.create(
            title="SF Issuu Magazine",
            slug="sf-issuu-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/magazine",
        )

        response = self.client.get(reverse("publications:pdf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="https://issuu.com/sfklubben/docs/magazine"')
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        self.assertNotContains(response, "data-pdf-url")


class PDFFileDetailTests(TestCase):
    def test_detail_redirects_to_external_url_after_access_checks(self):
        pdf_file = PDFFile.objects.create(
            title="SF Issuu Magazine",
            slug="sf-issuu-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/magazine",
        )

        response = self.client.get(reverse("publications:pdf_view", args=[pdf_file.slug]))

        self.assertRedirects(
            response,
            "https://issuu.com/sfklubben/docs/magazine",
            fetch_redirect_response=False,
        )

    def test_external_url_still_respects_login_requirement(self):
        pdf_file = PDFFile.objects.create(
            title="Members Magazine",
            slug="members-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/members",
            requires_login=True,
        )

        response = self.client.get(reverse("publications:pdf_view", args=[pdf_file.slug]))

        self.assertRedirects(
            response,
            reverse("members:login") + f"?next=/publications/{pdf_file.slug}/",
            fetch_redirect_response=False,
        )


class PDFFileModelTests(TestCase):
    def test_requires_file_or_redirect_url(self):
        pdf_file = PDFFile(title="Empty Publication", slug="empty-publication")

        with self.assertRaises(ValidationError):
            pdf_file.full_clean()
