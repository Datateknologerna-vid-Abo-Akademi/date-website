import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import re_path, reverse

from members.gdpr import anonymize_personal_data, collect_personal_data


class GDPRAdminMixin:
    """Adds GDPR export and erasure views to a ModelAdmin.

    The views are superuser-only. Export returns a JSON download of all
    personal data held for an email address; erasure runs the shared
    anonymization policy from ``members.gdpr`` with a dry-run preview step.
    """

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path(r'^gdpr/$', self.admin_site.admin_view(self.gdpr_view), name="members_gdpr"),
            re_path(r'^gdpr/export/$', self.admin_site.admin_view(self.gdpr_export_view), name="members_gdpr_export"),
        ]
        return custom_urls + urls

    def _require_superuser(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

    def gdpr_view(self, request):
        self._require_superuser(request)
        context = self.admin_site.each_context(request)
        context.update(
            {
                'opts': self.model._meta,
                'title': 'GDPR',
                'email': request.GET.get('email', '').strip(),
                'dry_run_summary': None,
            }
        )
        if request.method == 'POST':
            email = request.POST.get('email', '').strip()
            context['email'] = email
            if not email:
                messages.error(request, 'Ange en e-postadress.')
            elif request.POST.get('action') == 'preview':
                context['dry_run_summary'] = anonymize_personal_data(email, dry_run=True)
                messages.warning(request, 'Förhandsgranskning: inget har ändrats ännu.')
            elif request.POST.get('action') == 'erase':
                if request.POST.get('confirm') != '1':
                    context['dry_run_summary'] = anonymize_personal_data(email, dry_run=True)
                    context['confirm_erase'] = True
                    messages.warning(request, 'Bekräfta raderingen för att genomföra den.')
                else:
                    summary = anonymize_personal_data(email, dry_run=False)
                    messages.success(
                        request,
                        f"Raderat/anonymiserat data för {email}: {summary['members']} medlem(mar), "
                        f"{summary['attendees']} deltagarrad(er).",
                    )
                    return HttpResponseRedirect(request.path)
        return TemplateResponse(request, 'admin/members/gdpr.html', context)

    def gdpr_export_view(self, request):
        self._require_superuser(request)
        email = request.GET.get('email', '').strip()
        if not email:
            return HttpResponseRedirect(reverse('admin:members_gdpr'))
        data = collect_personal_data(email)
        payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        response = HttpResponse(payload, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="gdpr-{email}.json"'
        return response
