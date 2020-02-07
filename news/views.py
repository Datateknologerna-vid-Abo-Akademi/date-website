from django.shortcuts import render

from . import models

LATEST_NEWS_POSTS = 10


def index(request):
    latest_news = models.Post.objects.filter(published=True).order_by('modified_time').reverse()[:LATEST_NEWS_POSTS]
    return render(request, 'news/index.html', {'latest_news_items': latest_news})


def article(request, slug):
    post = models.Post.objects.filter(slug=slug, published=True)
    return render(request, 'news/article.html', {'article': post})


def author(request, author):
    articles = models.Post.objects.filter(author__username__exact=author, published=True).order_by('modified_time')
    return render(request, 'news/author.html', {'articles': articles})


def section(request):
    pass
