from django.contrib import admin
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from two_factor.admin import AdminSiteOTPRequiredMixin

# Remove standalone OTP device admins registered by django_otp — devices
# are managed through the Member inline instead.
for _model in (TOTPDevice, StaticDevice):
    try:
        admin.site.unregister(_model)
    except admin.sites.NotRegistered:
        pass


class FixedLanguageAdminSite(AdminSiteOTPRequiredMixin, admin.AdminSite):
    """Mirror the default admin site while preserving normal locale resolution."""

    def has_permission(self, request):
        if not admin.AdminSite.has_permission(self, request):
            return False

        # Allow access when the user has no 2FA device registered (2FA is optional).
        # When a device exists the user must have completed OTP verification this session.
        has_totp = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
        return request.user.is_verified() or not has_totp


admin_site = admin.site
