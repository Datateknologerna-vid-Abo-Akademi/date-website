from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib import admin
from django.test import TestCase

from harassment.admin import HarassmentAdmin, HarassmentEmailRecipientAdmin
from harassment.models import Harassment, HarassmentEmailRecipient


class HarassmentLegacyAdminPermissionTests(TestCase):
    def test_legacy_social_permissions_preserve_admin_access(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                has_module_perms=Mock(return_value=False),
                has_perm=Mock(side_effect=lambda permission: permission.startswith('social.')),
            )
        )

        report_admin = HarassmentAdmin(Harassment, admin.site)
        recipient_admin = HarassmentEmailRecipientAdmin(HarassmentEmailRecipient, admin.site)

        self.assertTrue(report_admin.has_module_permission(request))
        self.assertTrue(report_admin.has_view_permission(request))
        self.assertTrue(recipient_admin.has_change_permission(request))
