import instaloader
from itertools import chain, islice

from django.shortcuts import render
from django.views import View
from . import models
from ads.models import IgUrl

# Create your views here.

def adsIndex(request):
    ads = models.AdUrl.objects.all()
    return render(request, 'ads/adsindex.html', {'ads': ads})

def igUrl(request):
    L = instaloader.Instaloader()
    igProfile = instaloader.Profile.from_username(L.context, "kemistklubben")
    posts = igProfile.get_posts()
    top20 = islice(posts, 20)

    models.IgUrl.objects.all().delete()

    for post in top20:
        u = IgUrl(url=post.url,shortcode=post.shortcode)
        u.save()

    igPosts = IgUrl.objects.all()

    return render(request, 'ads/igurls.html', {'igurls':igPosts})