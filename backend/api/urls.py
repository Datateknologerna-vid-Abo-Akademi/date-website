from django.urls import path

from . import views


app_name = "api"

urlpatterns = [
    path("meta/site", views.SiteMetaApiView.as_view(), name="meta-site"),
    path("auth/session", views.SessionApiView.as_view(), name="auth-session"),
    path("auth/login", views.LoginApiView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutApiView.as_view(), name="auth-logout"),
    path("home", views.HomeApiView.as_view(), name="home"),
    path("news", views.NewsListApiView.as_view(), name="news-list"),
    path("news/<slug:slug>", views.NewsDetailApiView.as_view(), name="news-detail"),
    path("events", views.EventsListApiView.as_view(), name="events-list"),
    path("events/<slug:slug>", views.EventDetailApiView.as_view(), name="event-detail"),
    path("events/<slug:slug>/passcode", views.EventPasscodeApiView.as_view(), name="event-passcode"),
    path("events/<slug:slug>/signup", views.EventSignupApiView.as_view(), name="event-signup"),
    path("pages/<slug:slug>", views.StaticPageApiView.as_view(), name="static-page"),
]
