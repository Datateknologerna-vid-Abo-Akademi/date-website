from django.shortcuts import render

from . import models

def index(request):
    all_blogs = models.Blog.objects.all().reverse()
    return render(request, 'blog/index.html', {'all_blogs': all_blogs})

def detail(request, blog_id):
    blog = models.Blog.objects.get(id=blog_id)
    comments = models.Comment.objects.filter(blog__id=blog_id)
    return render(request, 'blog/detail.html', {'blog': blog, 'comments': comments})
