import requests
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.utils.translation import get_language
from django.views import View

import staticpages.models
from . import models
from .policy_content import EQUALITY_PLAN_URL, REGISTRATION_TERMS_CONTENT
from .policy_rendering import render_policy_document


def get_current_language_code():
    language = get_language() or "sv"
    return language.split("-")[0]


def equality_plan_view(request):
    if settings.PROJECT_NAME != "date":
        raise Http404()
    try:
        response = requests.get(EQUALITY_PLAN_URL, timeout=10)
        response.raise_for_status()
        markdown_text = response.text
        fetch_error = None
    except requests.RequestException:
        markdown_text = (
            "Jämlikhetsplanen kunde inte hämtas just nu.\n\n"
            "Försök igen om en stund eller öppna originaldokumentet direkt på GitHub."
        )
        fetch_error = EQUALITY_PLAN_URL

    return render_policy_document(request, "Jämlikhetsplan", markdown_text, fetch_error=fetch_error)


def registration_terms_view(request):
    if settings.PROJECT_NAME != "date":
        raise Http404()
    language_code = get_current_language_code()
    localized_content = REGISTRATION_TERMS_CONTENT.get(language_code, REGISTRATION_TERMS_CONTENT["sv"])
    return render_policy_document(
        request,
        localized_content["title"],
        localized_content["markdown"],
        show_page_title=True,
    )


class StaticPageView(View):
    def get(self, request, slug):
        page = get_object_or_404(models.StaticPage, slug=slug)
        show_content = not page.members_only or (page.members_only and request.user.is_authenticated)
        if show_content:
            return render(request, 'staticpages/staticpage.html', {'page': page, 'show_content': show_content})
        else:
            return redirect_to_login(request.get_full_path())
