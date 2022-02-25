from django.shortcuts import redirect, render
from django.views import View

from . import models

# Create your views here.

class StaticPageIndex(View):
    def get(self, request):
        pages = models.StaticPage.objects.all()
        return render(request, 'staticpages/staticpageindex.html', {'pages':pages})

class StaticPageView(View):
    def get(self, request, slug):
        page = models.StaticPage.objects.get(slug=slug)
        show_content = not page.members_only or (page.members_only and request.user.is_authenticated)
        if show_content:
            return render(request, 'staticpages/staticpage.html', {'page':page, 'show_content': show_content})
        else:
            return redirect('/members/login')

def staticUrl(request):
    staticUrls = models.StaticUrl.objects.all()
    return render(request, 'staticpages/staticUrls.html', {'staticUrls': staticUrls})
