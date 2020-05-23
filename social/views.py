import instaloader

from itertools import islice
from django.shortcuts import render
from . import models
from social.models import IgUrl
# Create your views here.

def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index':index})

def igUrls(request):
    L = instaloader.Instaloader()
    igProfile = instaloader.Profile.from_username(L.context, "kemistklubben")
    posts = igProfile.get_posts()
    top40 = islice(posts, 40)

    models.IgUrl.objects.all().delete()

    for post in top40:
        u = IgUrl(url=post.url,shortcode=post.shortcode)
        u.save()

    igPosts = IgUrl.objects.all()
    
    return render(request, 'social/igurls.html', {'igurls':igPosts})