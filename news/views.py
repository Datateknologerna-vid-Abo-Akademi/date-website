from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404,render

from . import models

def index(request):
    latest_news = models.Post.objects.order_by('modified_time')[:5]
    context = {
        'latest_news_items': latest_news,
    }
    return render(request, 'news/index.html', context)

def article(request, slug):
    article = get_object_or_404(models.Post, slug=slug)
    if article.published:
        return render(request, 'news/article.html', {'article': article})
    raise Http404("No Post matches the given query.")

def section(request):
    pass
