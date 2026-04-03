from django.contrib import admin
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.admin import AdminSiteOTPRequiredMixin


class FixedLanguageAdminSite(AdminSiteOTPRequiredMixin, admin.AdminSite):
    """Mirror the default admin site while preserving normal locale resolution."""

    def has_permission(self, request):
        if not admin.AdminSite.has_permission(self, request):
            return False

        # Allow access when the user has no 2FA device registered (2FA is optional).
        # When a device exists the user must have completed OTP verification this session.
        has_totp = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
        return request.user.is_verified() or not has_totp


admin_site = FixedLanguageAdminSite()

for model, model_admin in admin.site._registry.items():
    admin_site._registry[model] = model_admin.__class__(model, admin_site)
