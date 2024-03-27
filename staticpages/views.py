from django.shortcuts import redirect, render, get_object_or_404
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
            return redirect('/members/login')
