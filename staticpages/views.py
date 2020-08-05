from django.shortcuts import render
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
        return render(request, 'staticpages/staticpage.html', {'page':page})

def staticUrl(request):
    staticUrls = models.StaticUrl.objects.all()
    return render(request, 'staticpages/staticUrls.html', {'staticUrls': staticUrls})
