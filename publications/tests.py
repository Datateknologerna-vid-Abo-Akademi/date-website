from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import ORDINARY_MEMBER, SENIOR_MEMBER, MembershipType
from publications.admin import PublicationCollectionAdminForm
from publications.models import PDFFile, PublicationCollection


def create_collection(**kwargs):
    sequence = PublicationCollection.objects.count() + 1
    defaults = {
        "title": f"Publications {sequence}",
        "slug": f"publications-{sequence}",
    }
    defaults.update(kwargs)
    if kwargs:
        return PublicationCollection.objects.create(**defaults)
    collection, _ = PublicationCollection.objects.get_or_create(
        slug="publications",
        defaults={
            "title": "Publications",
        },
    )
    return collection


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
        PDFFile.objects.bulk_create(
            [
                PDFFile(
                    collection=create_collection(),
                    title="Broken PDF",
                    slug="broken-pdf",
                    file="pdfs/broken.pdf",
                    uploaded_at=timestamp,
                    updated_at=timestamp,
                )
            ]
        )
        pdf_file = PDFFile.objects.get(slug="broken-pdf")

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken storage"),
        ):
            response = self.client.get(reverse("admin:publications_pdffile_change", args=[pdf_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pdfs/broken.pdf")

    def test_change_page_shows_selected_collection_access_details(self):
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_PASSWORD)
        collection.set_password("secret")
        collection.save()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Locked Magazine",
            slug="locked-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/locked",
        )

        response = self.client.get(reverse("admin:publications_pdffile_change", args=[pdf_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selected collection access")
        self.assertContains(response, "Password protected")
        self.assertContains(response, "Password configured")
        self.assertContains(response, reverse("admin:publications_publicationcollection_change", args=[collection.pk]))

    def test_collection_access_endpoint_returns_selected_collection_details(self):
        senior = MembershipType.objects.get(pk=SENIOR_MEMBER)
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_MEMBERSHIP)
        collection.allowed_membership_types.add(senior)

        response = self.client.get(reverse("admin:publications_pdffile_collection_access", args=[collection.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], collection.title)
        self.assertEqual(response.json()["visibility"], PublicationCollection.VISIBILITY_MEMBERSHIP)
        self.assertEqual(response.json()["memberships"], [senior.name])

    def test_collection_access_endpoint_requires_publication_permission(self):
        staff_group = Group.objects.create(name="admin")
        staff_user = get_user_model().objects.create_user(
            username="staff-without-publications",
            password="pwd",
            email="staff-without-publications@example.com",
        )
        staff_user.groups.add(staff_group)
        self.client.force_login(staff_user)
        collection = create_collection()

        response = self.client.get(reverse("admin:publications_pdffile_collection_access", args=[collection.pk]))

        self.assertEqual(response.status_code, 403)


class PublicationCollectionAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="collection-admin",
            password="pwd",
            email="collection-admin@example.com",
        )
        self.client.force_login(self.admin_user)

    def test_change_page_manages_collection_access_and_publications_together(self):
        collection = create_collection()
        PDFFile.objects.create(
            collection=collection,
            title="Annual Magazine",
            slug="annual-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/annual",
        )

        response = self.client.get(reverse("admin:publications_publicationcollection_change", args=[collection.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Access Control")
        self.assertContains(response, "Annual Magazine")
        self.assertContains(response, "id_publications-0-title")
        self.assertRegex(
            response.content.decode(),
            r'<input type="file" name="publications-0-file" disabled id="id_publications-0-file">',
        )
        self.assertContains(response, "Publication list")

    def test_changelist_uses_singular_publication_count_label(self):
        collection = create_collection()
        PDFFile.objects.create(
            collection=collection,
            title="Annual Magazine",
            slug="annual-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/annual",
        )

        response = self.client.get(reverse("admin:publications_publicationcollection_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 publication")
        self.assertNotContains(response, "1 publications")

    def test_change_page_inline_renders_when_file_url_cannot_be_resolved(self):
        timestamp = timezone.now()
        PDFFile.objects.bulk_create(
            [
                PDFFile(
                    collection=create_collection(),
                    title="Broken PDF",
                    slug="broken-pdf",
                    file="pdfs/broken.pdf",
                    uploaded_at=timestamp,
                    updated_at=timestamp,
                )
            ]
        )
        collection = PublicationCollection.objects.get(slug="publications")

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken storage"),
        ):
            response = self.client.get(reverse("admin:publications_publicationcollection_change", args=[collection.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Broken PDF")

    def test_password_visibility_requires_password(self):
        form = PublicationCollectionAdminForm(
            data={
                "title": "Locked",
                "slug": "locked",
                "description": "",
                "visibility": PublicationCollection.VISIBILITY_PASSWORD,
                "cover_image": "",
                "allowed_membership_types": [],
                "password": "",
                "clear_password": "",
                "ordering": 0,
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_membership_visibility_requires_membership_type(self):
        form = PublicationCollectionAdminForm(
            data={
                "title": "Members",
                "slug": "members",
                "description": "",
                "visibility": PublicationCollection.VISIBILITY_MEMBERSHIP,
                "cover_image": "",
                "allowed_membership_types": [],
                "password": "",
                "clear_password": "",
                "ordering": 0,
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("allowed_membership_types", form.errors)


class PDFFileListTests(TestCase):
    def test_list_renders_when_file_url_cannot_be_resolved(self):
        timestamp = timezone.now()
        collection = create_collection()
        PDFFile.objects.bulk_create(
            [
                PDFFile(
                    collection=collection,
                    title="Broken PDF",
                    slug="broken-pdf",
                    file="pdfs/broken.pdf",
                    uploaded_at=timestamp,
                    updated_at=timestamp,
                )
            ]
        )

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=RuntimeError("broken storage"),
        ):
            response = self.client.get(collection.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Broken PDF")
        self.assertNotContains(response, "data-pdf-url")

    def test_list_links_redirect_publication_to_external_url(self):
        collection = create_collection()
        PDFFile.objects.create(
            collection=collection,
            title="SF Issuu Magazine",
            slug="sf-issuu-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/magazine",
        )

        response = self.client.get(collection.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/publications/publications/sf-issuu-magazine/"')
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        self.assertNotContains(response, "data-pdf-url")

    def test_index_lists_visible_collections_only(self):
        open_collection = create_collection(title="Open", slug="open")
        # Second visible collection so the index renders instead of
        # auto-redirecting to the lone visible collection.
        second_open = create_collection(title="Open Two", slug="open-two")
        hidden_collection = create_collection(
            title="Hidden",
            slug="hidden",
            visibility=PublicationCollection.VISIBILITY_HIDDEN,
        )
        members_collection = create_collection(
            title="Members",
            slug="members",
            visibility=PublicationCollection.VISIBILITY_LOGIN,
        )
        for collection, slug in (
            (open_collection, "open-publication"),
            (second_open, "open-two-publication"),
            (hidden_collection, "hidden-publication"),
            (members_collection, "members-publication"),
        ):
            PDFFile.objects.create(
                collection=collection,
                title=slug.replace("-", " ").title(),
                slug=slug,
                redirect_url="https://issuu.com/sfklubben/docs/magazine",
            )

        response = self.client.get(reverse("publications:pdf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open")
        self.assertNotContains(response, "Hidden")
        self.assertNotContains(response, "Members")

    def test_index_renders_collection_cover_image(self):
        collection = create_collection(
            title="A&O", slug="ao", cover_image="wordpress/sfklubben/wp-content/uploads/2022/04/aologo.png"
        )
        PDFFile.objects.create(
            collection=collection,
            title="A&O 01/2026",
            slug="ao-012026",
            redirect_url="https://issuu.com/sfklubben/docs/ao-1-2026",
        )
        # Second collection so the index renders instead of redirecting.
        other = create_collection(title="Other", slug="other")
        PDFFile.objects.create(
            collection=other,
            title="Other 1",
            slug="other-1",
            redirect_url="https://issuu.com/sfklubben/docs/other",
        )

        response = self.client.get(reverse("publications:pdf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="/media/wordpress/sfklubben/wp-content/uploads/2022/04/aologo.png"')

    def test_index_redirects_when_only_one_collection_visible(self):
        only = create_collection(title="Only", slug="only")
        PDFFile.objects.create(
            collection=only,
            title="Only 1",
            slug="only-1",
            redirect_url="https://issuu.com/sfklubben/docs/only",
        )

        response = self.client.get(reverse("publications:pdf_list"))

        self.assertRedirects(response, only.get_absolute_url())

    def test_index_hides_empty_collections(self):
        create_collection(title="Empty", slug="empty")

        response = self.client.get(reverse("publications:pdf_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Empty")


class PDFFileDetailTests(TestCase):
    def test_detail_redirects_to_external_url_after_access_checks(self):
        collection = create_collection()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="SF Issuu Magazine",
            slug="sf-issuu-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/magazine",
        )

        response = self.client.get(pdf_file.get_absolute_url())

        self.assertRedirects(
            response,
            "https://issuu.com/sfklubben/docs/magazine",
            fetch_redirect_response=False,
        )

    def test_external_url_still_respects_login_requirement(self):
        collection = create_collection()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Members Magazine",
            slug="members-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/members",
            requires_login=True,
        )

        response = self.client.get(pdf_file.get_absolute_url())

        self.assertRedirects(
            response,
            reverse("members:login") + f"?next=/publications/publications/{pdf_file.slug}/",
            fetch_redirect_response=False,
        )

    def test_legacy_detail_redirects_to_canonical_collection_url_after_access_checks(self):
        collection = create_collection()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="SF Issuu Magazine",
            slug="sf-issuu-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/magazine",
        )

        response = self.client.get(f"/publications/{pdf_file.slug}/")

        self.assertRedirects(
            response,
            pdf_file.get_absolute_url(),
            status_code=301,
            target_status_code=302,
            fetch_redirect_response=False,
        )

    def test_hidden_collection_is_not_accessible_by_direct_link(self):
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_HIDDEN)
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Hidden Magazine",
            slug="hidden-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/hidden",
        )

        response = self.client.get(pdf_file.get_absolute_url())

        self.assertEqual(response.status_code, 404)

    def test_membership_collection_requires_allowed_membership_type(self):
        ordinary = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        senior = MembershipType.objects.get(pk=SENIOR_MEMBER)
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_MEMBERSHIP)
        collection.allowed_membership_types.add(senior)
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Senior Magazine",
            slug="senior-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/senior",
        )
        user = get_user_model().objects.create_user(
            username="ordinary",
            password="pwd",
            membership_type=ordinary,
        )
        self.client.force_login(user)

        response = self.client.get(pdf_file.get_absolute_url())

        self.assertEqual(response.status_code, 404)

    def test_password_collection_prompts_until_password_is_entered(self):
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_PASSWORD)
        collection.set_password("secret")
        collection.save()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Locked Magazine",
            slug="locked-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/locked",
        )

        response = self.client.get(pdf_file.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lösenord")

        response = self.client.post(pdf_file.get_absolute_url(), {"password": "secret"})
        self.assertRedirects(response, pdf_file.get_absolute_url(), fetch_redirect_response=False)

        response = self.client.get(pdf_file.get_absolute_url())
        self.assertRedirects(
            response,
            "https://issuu.com/sfklubben/docs/locked",
            fetch_redirect_response=False,
        )

    def test_password_rotation_invalidates_existing_session_access(self):
        collection = create_collection(visibility=PublicationCollection.VISIBILITY_PASSWORD)
        collection.set_password("secret")
        collection.save()
        pdf_file = PDFFile.objects.create(
            collection=collection,
            title="Rotating Magazine",
            slug="rotating-magazine",
            redirect_url="https://issuu.com/sfklubben/docs/rotating",
        )

        self.client.post(pdf_file.get_absolute_url(), {"password": "secret"})
        response = self.client.get(pdf_file.get_absolute_url())
        self.assertEqual(response.status_code, 302)

        collection.set_password("new-secret")
        collection.save()

        response = self.client.get(pdf_file.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lösenord")


class PDFFileModelTests(TestCase):
    def test_requires_file_or_redirect_url(self):
        pdf_file = PDFFile(title="Empty Publication", slug="empty-publication")

        with self.assertRaises(ValidationError):
            pdf_file.full_clean()
