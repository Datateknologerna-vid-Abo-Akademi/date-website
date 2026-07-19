from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from . import models

LATEST_NEWS_POSTS = 10


def _paginate(request, queryset):
    paginator = Paginator(queryset, LATEST_NEWS_POSTS)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def _page_window(page_obj, window=2):
    current = page_obj.number
    total = page_obj.paginator.num_pages
    start = max(1, current - window)
    end = min(total, current + window)
    return {
        'page_range_window': range(start, end + 1),
        'show_first_page': start > 1,
        'show_last_page': end < total,
        'show_first_ellipsis': start > 2,
        'show_last_ellipsis': end < total - 1,
    }


def index(request):
    queryset = models.Post.objects.published().filter(category__isnull=True).order_by('-published_time', '-pk')
    page_obj = _paginate(request, queryset)
    return render(request, 'news/index.html', {'latest_news_items': page_obj, **_page_window(page_obj)})


def article(request, slug):
    post = get_object_or_404(models.Post.objects.published(), slug=slug, category__isnull=True)
    return render(request, 'news/article.html', {'article': post})


def author(request, author):
    articles = models.Post.objects.published().filter(author__username__exact=author).order_by('-published_time', '-pk')
    return render(request, 'news/author.html', {'articles': articles})


def category_index(request, category):
    queryset = models.Post.objects.published().filter(category__slug=category).order_by('-published_time', '-pk')
    page_obj = _paginate(request, queryset)
    return render(request, 'news/index.html', {'latest_news_items': page_obj, **_page_window(page_obj)})


def category_article(request, category, slug):
    post = get_object_or_404(models.Post.objects.published(), slug=slug, category__slug=category)
    return render(request, 'news/article.html', {'article': post})
