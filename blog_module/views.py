from django.shortcuts import render

from . import models

def index(request):
    all_blogs = models.Blog.objects.all()
    return render(request, 'index.html', {'all_blogs': all_blogs})

def detail(request, blog_id):
    blog = models.Blog.objects.get(id=blog_id)
    comments = models.Comment.objects.filter(blog_id=blog_id)
    return render(request, 'detail.html', {'blog': blog, 'comments': comments})