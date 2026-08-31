import json
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import re_path, reverse
from django.utils.http import content_disposition_header
from django.utils.translation import gettext as _

from members.gdpr import anonymize_personal_data, collect_personal_data

_PREVIEW_SESSION_KEY = 'gdpr_preview_email'


class GDPRAdminMixin:
    """Adds GDPR export and erasure views to a ModelAdmin.

    The views are superuser-only. Export returns a JSON download of all
    personal data held for an email address; erasure runs the shared
    anonymization policy from ``members.gdpr``. Erasure is only accepted
    after a server-side preview was shown for the same email in this
    session.
    """

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path(r'^gdpr/$', self.admin_site.admin_view(self.gdpr_view), name="members_gdpr"),
            re_path(
                r'^gdpr/export/$',
                self.admin_site.admin_view(self.gdpr_export_view),
                name="members_gdpr_export",
            ),
        ]
        return custom_urls + urls

    def _require_superuser(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

    def _clean_email(self, raw):
        email = (raw or '').strip()
        if not email:
            return ''
        try:
            validate_email(email)
        except ValidationError:
            return None
        return email

    def gdpr_view(self, request):
        self._require_superuser(request)
        context = self.admin_site.each_context(request)
        context.update(
            {
                'opts': self.model._meta,
                'title': 'GDPR',
                'email': request.GET.get('email', '').strip(),
                'dry_run_summary': None,
                'confirm_erase': False,
            }
        )
        if request.method == 'POST':
            return self._handle_post(request, context)
        return TemplateResponse(request, 'admin/members/gdpr.html', context)

    def _handle_post(self, request, context):
        email = self._clean_email(request.POST.get('email'))
        context['email'] = email or ''
        action = request.POST.get('action')

        if email is None:
            messages.error(request, _('Ogiltig e-postadress.'))
        elif not email:
            messages.error(request, _('Ange en e-postadress.'))
        elif action == 'export':
            return HttpResponseRedirect(reverse('admin:members_gdpr_export') + '?' + urlencode({'email': email}))
        elif action == 'erase':
            previewed = request.session.get(_PREVIEW_SESSION_KEY)
            if request.POST.get('confirm') == '1' and previewed == email:
                summary = anonymize_personal_data(email, dry_run=False)
                request.session.pop(_PREVIEW_SESSION_KEY, None)
                messages.success(
                    request,
                    _(
                        'Raderat/anonymiserat data för %(email)s: %(members)s medlem(mar), '
                        '%(attendees)s deltagarrad(er).'
                    )
                    % {'email': email, 'members': summary['members'], 'attendees': summary['attendees']},
                )
                return HttpResponseRedirect(request.path)
            context['dry_run_summary'] = anonymize_personal_data(email, dry_run=True)
            context['confirm_erase'] = True
            request.session[_PREVIEW_SESSION_KEY] = email
            messages.warning(request, _('Bekräfta raderingen för att genomföra den. Inget har ändrats ännu.'))
        elif action == 'preview':
            context['dry_run_summary'] = anonymize_personal_data(email, dry_run=True)
            context['confirm_erase'] = True
            request.session[_PREVIEW_SESSION_KEY] = email
            messages.info(request, _('Förhandsgranskning: inget har ändrats ännu. Bekräfta för att radera.'))
        else:
            context['dry_run_summary'] = anonymize_personal_data(email, dry_run=True)
            messages.info(request, _('Förhandsgranskning: inget har ändrats ännu.'))
        return TemplateResponse(request, 'admin/members/gdpr.html', context)

    def gdpr_export_view(self, request):
        self._require_superuser(request)
        email = self._clean_email(request.GET.get('email'))
        if not email:
            return HttpResponseRedirect(reverse('admin:members_gdpr'))
        data = collect_personal_data(email)
        payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        response = HttpResponse(payload, content_type='application/json')
        response['Content-Disposition'] = content_disposition_header('attachment', 'gdpr-export.json')
        return response
