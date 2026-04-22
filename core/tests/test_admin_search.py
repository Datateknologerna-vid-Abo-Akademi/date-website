from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminSearchSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@example.com",
        )
        self.client.force_login(self.user)

    def test_changed_admin_searches_render(self):
        admin_url_names = [
            "admin:archive_documentcollection_changelist",
            "admin:archive_examcollection_changelist",
            "admin:archive_picturecollection_changelist",
            "admin:billing_eventbillingconfiguration_changelist",
            "admin:billing_eventinvoice_changelist",
            "admin:ctf_ctf_changelist",
            "admin:ctf_flag_changelist",
            "admin:ctf_guess_changelist",
            "admin:events_event_changelist",
            "admin:events_eventattendees_changelist",
            "admin:members_functionary_changelist",
            "admin:members_member_changelist",
            "admin:members_subscriptionpayment_changelist",
            "admin:news_category_changelist",
            "admin:news_post_changelist",
            "admin:polls_question_changelist",
            "admin:publications_pdffile_changelist",
            "admin:staticpages_staticpage_changelist",
            "admin:staticpages_staticpagenav_changelist",
        ]

        for url_name in admin_url_names:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), {"q": "needle"})
                self.assertEqual(response.status_code, 200)

    def test_archive_cleanup_button_renders_on_archive_changelists(self):
        for url_name in [
            "admin:archive_documentcollection_changelist",
            "admin:archive_examcollection_changelist",
            "admin:archive_picturecollection_changelist",
        ]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, reverse("archive:cleanMedia"))
