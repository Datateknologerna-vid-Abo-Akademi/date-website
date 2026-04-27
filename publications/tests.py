from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
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
