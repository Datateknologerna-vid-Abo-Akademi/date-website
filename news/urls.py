from django.urls import path

from . import feed, views

app_name = 'news'

urlpatterns = [
    path('feed/', feed.LatestPosts()),
    path('', views.index, name='index'),
    path('aa/', views.aa_index, name='aa_index'),
    path('articles/<slug:slug>/', views.article, name='detail'),
    path('aa/<slug:slug>/', views.aa_article, name='aa_detail'),
    path('articles/<slug:slug>/<int:section>/', views.section, name='section'),
    path('author/<slug:author>/', views.author, name='author'),
]
