from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import EventBillingConfiguration, EventInvoice
from billing.util import BillingIntegrations
from ctf.models import Ctf
from events.models import Event, EventAttendees
from functionaries.models import Functionary, FunctionaryRole
from publications.models import PublicationCollection
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


class AdminUxLinkTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin-ux",
            password="pass",
            email="admin-ux@example.com",
        )
        self.client.force_login(self.admin_user)

    def test_billing_configuration_links_event_and_invoices(self):
        event = Event.objects.create(
            title="Paid Event",
            slug="paid-event",
            author=self.admin_user,
        )
        attendee = EventAttendees.objects.create(
            event=event,
            user="Ada Admin",
            email="ada@example.com",
        )
        EventBillingConfiguration.objects.create(
            event=event,
            due_date=timezone.localdate(),
            integration_type=BillingIntegrations.INVOICE.value,
            price="12",
        )
        EventInvoice.objects.create(
            participant=attendee,
            invoice_number=1001,
            reference_number="12345",
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate(),
            amount=12,
        )

        response = self.client.get(reverse("admin:billing_eventbillingconfiguration_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin:events_event_change", args=[event.pk]))
        self.assertContains(response, reverse("admin:billing_eventinvoice_changelist"))
        self.assertContains(response, "All invoices")
        self.assertContains(response, "1 invoice")

    def test_functionary_role_page_includes_assignments_inline(self):
        role = FunctionaryRole.objects.create(title="Treasurer", board=True)
        Functionary.objects.create(functionary_role=role, name="Ada Admin", year=2026)

        response = self.client.get(reverse("admin:functionaries_functionaryrole_change", args=[role.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Admin")
        self.assertContains(response, "id_functionary_set-0-name")

    def test_functionary_role_changelist_uses_singular_count_label(self):
        role = FunctionaryRole.objects.create(title="Treasurer", board=True)
        Functionary.objects.create(functionary_role=role, name="Ada Admin", year=2026)

        response = self.client.get(reverse("admin:functionaries_functionaryrole_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 functionary")
        self.assertNotContains(response, "1 functionaries")
        self.assertContains(response, reverse("admin:functionaries_functionary_changelist"))
        self.assertContains(response, "All assignments")

    def test_publication_collection_changelist_links_global_pdf_list(self):
        PublicationCollection.objects.create(title="A&O", slug="ao")

        response = self.client.get(reverse("admin:publications_publicationcollection_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin:publications_pdffile_changelist"))
        self.assertContains(response, "All PDF publications")

    def test_ctf_changelist_links_global_guess_list(self):
        Ctf.objects.create(title="Spring CTF", slug="spring-ctf")

        response = self.client.get(reverse("admin:ctf_ctf_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin:ctf_guess_changelist"))
        self.assertContains(response, "All guesses")

    def test_static_pages_admin_exposes_public_and_navigation_links(self):
        StaticPage.objects.create(title="About", slug="about")
        nav = StaticPageNav.objects.create(
            category_name="About menu",
            nav_element=10,
            use_category_url=True,
            url="/pages/about/",
        )
        StaticUrl.objects.create(category=nav, title="About page", url="/pages/about/", dropdown_element=10)

        page_response = self.client.get(reverse("admin:staticpages_staticpage_changelist"))
        nav_response = self.client.get(reverse("admin:staticpages_staticpagenav_change", args=[nav.pk]))

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "/pages/about/")
        self.assertEqual(nav_response.status_code, 200)
        self.assertContains(nav_response, "About page")
        self.assertContains(nav_response, 'href="/pages/about/"')
