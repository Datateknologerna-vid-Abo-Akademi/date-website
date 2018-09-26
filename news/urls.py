from django.urls import path

from . import feed, views

urlpatterns = [
    path('feed/', feed.LatestPosts()),
    path('', views.index, name='news_index'),
    path('articles/<slug:slug>/', views.article, name='article_detail'),
    path('articles/<slug:slug>/<int:section>/', views.section, name='article_section'),
    path('author/<slug:author>/', views.author, name='article_author'),
]
