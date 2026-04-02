from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render, get_object_or_404
from django.views import View

import staticpages.models
from . import models


class StaticPageView(View):
    def get(self, request, slug):
        page = get_object_or_404(models.StaticPage, slug=slug)
        show_content = not page.members_only or (page.members_only and request.user.is_authenticated)
        if show_content:
            return render(request, 'staticpages/staticpage.html', {'page': page, 'show_content': show_content})
        else:
            return redirect_to_login(request.get_full_path())
