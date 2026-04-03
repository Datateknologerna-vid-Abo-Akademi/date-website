from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


class TwoFactorRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect_to_two_factor(request):
            query_string = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('members:two_factor_verify')}?{query_string}")
        return self.get_response(request)

    def _should_redirect_to_two_factor(self, request):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return False
        if not getattr(user, "has_2fa_enabled", False):
            return False
        if request.session.get("two_factor_verified_user_id") == user.pk:
            return False

        verify_path = reverse("members:two_factor_verify")
        exempt_paths = {
            verify_path,
            reverse("logout"),
        }
        if request.path in exempt_paths:
            return False
        return True
