from django.urls import path, re_path

from . import views

app_name = 'staticpages'

urlpatterns = [
    path('registration-terms/', views.registration_terms_view, name='registration_terms'),
    path('equality-plan/', views.equality_plan_view, name='equality_plan'),
    re_path(r'^(?P<slug>[-\w]+)/$', views.StaticPageView.as_view(), name='page'),
]
