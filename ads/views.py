from django.shortcuts import render

from . import models

# Create your views here.


def adsIndex(request):
    ads = models.AdUrl.objects.all()
    return render(request, 'ads/adsindex.html', {'ads': ads})
