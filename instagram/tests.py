from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib import admin
from django.test import TestCase

from instagram.admin import IgUrlAdmin
from instagram.models import IgUrl


class InstagramLegacyAdminPermissionTests(TestCase):
    def test_legacy_social_permissions_preserve_admin_access(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                has_module_perms=Mock(return_value=False),
                has_perm=Mock(side_effect=lambda permission: permission.startswith('social.')),
            )
        )
        model_admin = IgUrlAdmin(IgUrl, admin.site)

        self.assertTrue(model_admin.has_module_permission(request))
        self.assertTrue(model_admin.has_change_permission(request))
