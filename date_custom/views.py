from django.views.generic.edit import CreateView

from core.utils import validate_captcha
from date_custom.forms import MembershipSignupForm
from date_custom.models import MembershipSignupRequest
from members.models import Member


class MembershipSignupRequestView(CreateView):
    model = MembershipSignupRequest
    form_class = MembershipSignupForm
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_data'] = {}
        if self.request.user.is_authenticated:
            user: Member = self.request.user
            user_data = {
                'full_name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'phone_number': user.phone,
                'street_address': user.address,
                'postal_code': user.zip_code,
                'city': user.city,
                'country': user.country,
            }

            context['user_data'] = user_data
        return context

    def form_valid(self, form):
        if not validate_captcha(self.request.POST.get('cf-turnstile-response', '')):
            form.add_error(None, "Captcha-valideringen misslyckades. Försök igen.")
            return self.form_invalid(form)
        form.instance.created_by = self.request.user
        return super().form_valid(form)
