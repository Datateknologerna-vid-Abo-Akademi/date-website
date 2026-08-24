from datetime import date, timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.handlers import handle_event_billing
from billing.models import EventBillingConfiguration, EventInvoice
from billing.util import BillingIntegrations, get_selection_price, send_event_free_confirmation, send_event_invoice
from events.models import Event, EventAttendees, EventRegistrationForm
from members.models import ORDINARY_MEMBER, Member, MembershipType


class BillingBaseTestCase(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.create(
            name="Ordinary",
            permission_profile=ORDINARY_MEMBER,
        )
        self.author = Member.objects.create_user(
            username="author",
            password="pwd",
            membership_type=self.membership_type,
        )
        now = timezone.now()
        self.event = Event.objects.create(
            title="Test Event",
            slug="test-event",
            author=self.author,
            sign_up_deadline=now + timezone.timedelta(days=7),
            sign_up_members=now - timezone.timedelta(days=1),
            sign_up_others=now - timezone.timedelta(days=1),
        )

    def create_attendee(self, email="participant@example.com", preferences=None):
        return EventAttendees.objects.create(
            event=self.event,
            user="Participant",
            email=email,
            preferences=preferences or {},
            anonymous=False,
            time_registered=timezone.now(),
        )

    def configure_billing(self, **overrides):
        defaults = {
            "event": self.event,
            "due_date": date.today() + timedelta(days=14),
            "integration_type": BillingIntegrations.INVOICE.value,
            "price": "12.50",
            "price_selector": "",
        }
        defaults.update(overrides)
        return EventBillingConfiguration.objects.create(**defaults)


class BillingAdminTests(BillingBaseTestCase):
    def setUp(self):
        super().setUp()
        self.config = self.configure_billing()

    def test_export_returns_404_for_missing_configuration(self):
        admin_user = get_user_model().objects.create_superuser(
            username='billing-admin',
            password='pwd',
            email='billing-admin@example.com',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:billing_ref_numbers', args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_export_requires_configuration_and_invoice_view_permissions(self):
        staff_group = Group.objects.create(name='admin')
        staff_user = get_user_model().objects.create_user(username='limited-billing-admin', password='pwd')
        staff_user.groups.add(staff_group)
        staff_user.user_permissions.add(Permission.objects.get(codename='view_eventbillingconfiguration'))
        self.client.force_login(staff_user)

        response = self.client.get(reverse('admin:billing_ref_numbers', args=[self.config.pk]))

        self.assertEqual(response.status_code, 403)
        request = RequestFactory().get(reverse('admin:billing_eventbillingconfiguration_changelist'))
        request.user = staff_user
        list_display = admin.site._registry[EventBillingConfiguration].get_list_display(request)
        self.assertNotIn('invoice_count', list_display)
        self.assertNotIn('ref_export', list_display)


class HandleEventBillingTests(BillingBaseTestCase):
    def test_creates_invoice_and_sends_email(self):
        self.configure_billing(price="42")
        signup = self.create_attendee()

        with (
            patch("billing.handlers.send_event_invoice") as mock_send_invoice,
            patch("billing.handlers.generate_invoice_number", return_value=24000042),
        ):
            handle_event_billing(signup)

        invoice = EventInvoice.objects.get(participant=signup)
        self.assertEqual(invoice.amount, 42)
        self.assertEqual(invoice.invoice_number, 24000042)
        mock_send_invoice.assert_called_once_with(signup, invoice)

    def test_sends_free_confirmation_when_price_is_zero(self):
        self.configure_billing(price="0")
        signup = self.create_attendee(email="free@example.com")

        with patch("billing.handlers.send_event_free_confirmation") as mock_free_confirmation:
            handle_event_billing(signup)

        self.assertFalse(EventInvoice.objects.exists())
        mock_free_confirmation.assert_called_once_with(signup)

    def test_returns_without_invoice_when_price_unavailable(self):
        self.configure_billing(price="invalid-number")
        signup = self.create_attendee(email="missing@example.com")

        with (
            patch("billing.handlers.send_event_free_confirmation") as mock_free_confirmation,
            patch("billing.handlers.send_event_invoice") as mock_send_invoice,
        ):
            handle_event_billing(signup)

        self.assertFalse(EventInvoice.objects.exists())
        mock_free_confirmation.assert_not_called()
        mock_send_invoice.assert_not_called()

    def test_retries_invoice_creation_after_failure(self):
        self.configure_billing(price="25")
        signup = self.create_attendee(email="retry@example.com")
        original_save = EventInvoice.save
        call_state = {"calls": 0}

        def flaky_save(self, *args, **kwargs):
            if call_state["calls"] == 0:
                call_state["calls"] += 1
                raise Exception("temporary failure")
            call_state["calls"] += 1
            return original_save(self, *args, **kwargs)

        with (
            patch("billing.handlers.EventInvoice.save", new=flaky_save),
            patch("billing.handlers.send_event_invoice") as mock_send_invoice,
        ):
            handle_event_billing(signup)

        self.assertEqual(call_state["calls"], 2)
        self.assertEqual(EventInvoice.objects.count(), 1)
        invoice = EventInvoice.objects.first()
        mock_send_invoice.assert_called_once_with(signup, invoice)


class GetSelectionPriceTests(BillingBaseTestCase):
    def test_returns_float_when_no_selector(self):
        price = get_selection_price(self.event, "15.5", None, {})
        self.assertEqual(price, 15.5)

    def test_returns_matching_choice_price(self):
        EventRegistrationForm.objects.create(
            event=self.event,
            name="ticket_type",
            type="select",
            choice_list="standard,student",
        )
        price = get_selection_price(
            self.event,
            "25,10",
            "ticket_type",
            {"ticket_type": "student"},
        )
        self.assertEqual(price, 10.0)

    def test_falls_back_to_flat_price_when_selector_missing(self):
        price = get_selection_price(
            self.event,
            "30.0",
            "does_not_exist",
            {},
        )
        self.assertEqual(price, 30.0)

    def test_raises_for_unknown_preference(self):
        EventRegistrationForm.objects.create(
            event=self.event,
            name="meal",
            type="select",
            choice_list="veg,meat",
        )
        with self.assertRaises(ValueError):
            get_selection_price(self.event, "10,15", "meal", {"meal": "fish"})


@override_settings(
    BILLING_CONTEXT={
        "INVOICE_RECIPIENT": "Datateknologerna",
        "IBAN": "FI00 0000 0000 0000",
        "BIC": "NDEAFIHH",
    },
    DEFAULT_FROM_EMAIL="billing@example.com",
)
class BillingEmailTests(BillingBaseTestCase):
    def setUp(self):
        super().setUp()
        self.attendee = self.create_attendee()

    @patch("billing.util.render_to_string", return_value="formatted-body")
    @patch("billing.util.send_email_task")
    def test_send_event_invoice_enqueues_email(self, mock_send_email, mock_render):
        invoice = EventInvoice.objects.create(
            participant=self.attendee,
            invoice_number=123,
            reference_number="1230",
            invoice_date=date.today(),
            due_date=date.today(),
            amount=55,
        )

        send_event_invoice(self.attendee, invoice)

        mock_render.assert_called_once()
        mock_send_email.delay.assert_called_once_with(
            f"{self.event.title} - Betalningsuppgifter",
            "formatted-body",
            "billing@example.com",
            [self.attendee.email],
        )

    @patch("billing.util.render_to_string", return_value="free-body")
    @patch("billing.util.send_email_task")
    def test_send_event_free_confirmation_enqueues_email(self, mock_send_email, mock_render):
        send_event_free_confirmation(self.attendee)

        mock_render.assert_called_once()
        mock_send_email.delay.assert_called_once_with(
            f"{self.event.title} - Bekräftelse",
            "free-body",
            "billing@example.com",
            [self.attendee.email],
        )
