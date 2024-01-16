from django.urls import path, re_path
from django.views.decorators.cache import cache_page

from . import views

app_name = 'staticpages'

urlpatterns = [
    re_path(r'^(?P<slug>[-\w]+)/$', cache_page(60)(views.StaticPageView.as_view()), name='page'),
]
