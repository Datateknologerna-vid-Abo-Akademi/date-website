from django.views.generic.edit import CreateView

from date_custom.models import MembershipSignupRequest


class MembershipSignupRequestView(CreateView):
    model = MembershipSignupRequest
    fields = [field.name for field in MembershipSignupRequest._meta.fields if field.name not in (
        'created_at', 'created_by')]
    success_url = "/"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
