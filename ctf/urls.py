from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = 'ctf'
urlpatterns = [
    path('', login_required(views.IndexView.as_view()), name='index'),
    # The literal `post-mortem` patterns must stay above the `<slug:...>` patterns:
    # `post-mortem` is itself a valid slug, so a later match could never be reached.
    path('post-mortem', login_required(views.PostMortemIndexView.as_view()), name='post_mortem_index'),
    path(
        'post-mortem/<slug:ctf_slug>',
        login_required(views.PostMortemDetailView.as_view()),
        name='post_mortem_detail',
    ),
    path('<slug:slug>', login_required(views.DetailView.as_view()), name='detail'),
    path('<slug:ctf_slug>/<slug:flag_slug>', login_required(views.flag), name='flag_detail'),
]
