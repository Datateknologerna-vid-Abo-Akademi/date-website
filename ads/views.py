from django.shortcuts import render
from django.views import View
from . import models

# Create your views here.

class AdsIndex(View):
    def get(self, request):
        ads = models.AdUrl.objects.all()
        return render(request, 'ads/adsindex.html', {'ads':ads})