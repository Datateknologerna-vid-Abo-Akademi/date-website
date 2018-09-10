from django.shortcuts import render

from . import models

LATEST_NEWS_POSTS = 5

def index(request):
    latest_news = models.Post.objects.filter(published=True).order_by('modified_time')[:LATEST_NEWS_POSTS]
    return render(request, 'news/index.html', {'latest_news_items': latest_news})

def article(request, slug):
    articles =  models.Post.objects.filter(slug=slug, published=True).order_by('modified_time')
    return render(request, 'news/article.html', {'articles': articles})

def author(request, author):
    articles = models.Post.objects.filter(author__username__exact=author, published=True).order_by('modified_time')
    return render(request, 'news/article.html', {'articles': articles})

def section(request):
    pass
