import json
from django.views.generic.edit import CreateView

from date_custom.models import MembershipSignupRequest
from members.models import Member


class MembershipSignupRequestView(CreateView):
    model = MembershipSignupRequest
    fields = [field.name for field in MembershipSignupRequest._meta.fields if field.name not in (
        'created_at', 'created_by')]
    success_url = "/"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name, field in form.fields.items():
            if MembershipSignupRequest._meta.get_field(field_name).blank:
                field.required = False
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            user: Member = self.request.user
            user_data = {
                'full_name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'phone_number': user.phone,
                'street_address': user.address,
                'postal_code': user.zip_code,
                'city': user.city,
                'country': user.country
            }

            context['user_data'] = json.dumps(user_data)
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
