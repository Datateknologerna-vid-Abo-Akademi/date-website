from django.shortcuts import render
from django.core.paginator import Paginator

from . import models

LATEST_NEWS_POSTS = 10


def index(request):
    latest_news = models.Post.objects.filter(published=True).reverse()
    paginator = Paginator(latest_news, LATEST_NEWS_POSTS)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)  
    return render(request, 'news/index.html', {'latest_news_items': page_obj})
    

def article(request, slug):
    post = models.Post.objects.get(slug=slug, published=True)
    return render(request, 'news/article.html', {'article': post})


def author(request, author):
    articles = models.Post.objects.filter(author__username__exact=author, published=True).order_by('modified_time')
    return render(request, 'news/author.html', {'articles': articles})


def section(request):
    pass
