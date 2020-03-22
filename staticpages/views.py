from django.shortcuts import render
from django.views import View
from . import models

# Create your views here.

class StaticPageIndex(View):
    def get(self, request):
        pages = models.StaticPage.objects.all()
        return render(request, 'staticpageindex.html', {'pages':pages})

class StaticPageView(View):
    def get(self, request, slug):
        page = models.StaticPage.objects.get(slug=slug)
        return render(request, 'staticpage.html', {'page':page})