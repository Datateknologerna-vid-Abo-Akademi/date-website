from django.shortcuts import render, get_object_or_404
from .models import Blog, Comment

# Create your views here.


def index(request):
    blogs = Blog.objects.all()
    context = {
        'all_blogs': blogs
    }
    return render(request, 'blog_tutorial/index.html', context)


def detail(request, blog_id):
    blog = get_object_or_404(Blog, pk=blog_id)
    comments = Comment.objects.filter(blog=blog_id)

    context = {
        'blog': blog,
        'comments': comments
    }

    return render(request, 'blog_tutorial/detail.html', context)