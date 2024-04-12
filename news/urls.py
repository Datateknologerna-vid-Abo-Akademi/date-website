from django.urls import path, re_path

from . import feed, views

app_name = 'news'

urlpatterns = [
    path('feed/', feed.LatestPosts()),
    path('', views.index, name='index'),
    path('<slug:category>/', views.category_index, name='aa_index'),
    path('articles/<slug:slug>/', views.article, name='detail'),
    path('<slug:category>/<slug:slug>/', views.category_article, name='detail'),
    # This is a mess because of lack of username validation
    re_path(r'author/(?P<author>[\w\s.@\u00C0-\u00FF\u00C5\u00C4\u00D6\u00E5\u00E4\u00F6-]+)/$', views.author,
            name='author'),
]
