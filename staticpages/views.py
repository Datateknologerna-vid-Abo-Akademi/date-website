from django.shortcuts import render
from django.views import View
from . import models

# Create your views here.

class StaticPageView(View):
    def get(self, request, slug):
        page = models.StaticPage.objects.get(slug=slug)

        return render(request, 'staticpages/staticpage.html', {'page':page})