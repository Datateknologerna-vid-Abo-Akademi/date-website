from django.urls import path

from . import feed, views

urlpatterns = [
    path('feed/', feed.LatestPosts()),
    path('', views.index, name='index'),
    path('articles/<slug:slug>/', views.article, name='article-detail'),
    path('articles/<slug:slug>/<int:section>/', views.section, name='article-section'),
    path('author/<slug:author>/', views.author, name='article-author'),
]
