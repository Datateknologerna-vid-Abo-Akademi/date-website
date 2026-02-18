from django.urls import path

from . import views


app_name = "api"

urlpatterns = [
    path("meta/site", views.SiteMetaApiView.as_view(), name="meta-site"),
    path("auth/session", views.SessionApiView.as_view(), name="auth-session"),
    path("auth/login", views.LoginApiView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutApiView.as_view(), name="auth-logout"),
    path("auth/signup", views.SignupApiView.as_view(), name="auth-signup"),
    path("home", views.HomeApiView.as_view(), name="home"),
    path("news", views.NewsListApiView.as_view(), name="news-list"),
    path("news/<slug:slug>", views.NewsDetailApiView.as_view(), name="news-detail"),
    path("events", views.EventsListApiView.as_view(), name="events-list"),
    path("events/<slug:slug>", views.EventDetailApiView.as_view(), name="event-detail"),
    path("events/<slug:slug>/passcode", views.EventPasscodeApiView.as_view(), name="event-passcode"),
    path("events/<slug:slug>/signup", views.EventSignupApiView.as_view(), name="event-signup"),
    path("pages/<slug:slug>", views.StaticPageApiView.as_view(), name="static-page"),
    path("members/me", views.MemberProfileApiView.as_view(), name="member-profile"),
    path("members/functionary-roles", views.FunctionaryRolesApiView.as_view(), name="functionary-roles"),
    path("members/functionaries", views.PublicFunctionariesApiView.as_view(), name="functionaries-public"),
    path("members/me/functionaries", views.MemberFunctionariesApiView.as_view(), name="member-functionaries"),
    path(
        "members/me/functionaries/<int:functionary_id>",
        views.MemberFunctionaryDetailApiView.as_view(),
        name="member-functionary-detail",
    ),
    path("polls", views.PollListApiView.as_view(), name="polls-list"),
    path("polls/<int:poll_id>", views.PollDetailApiView.as_view(), name="polls-detail"),
    path("polls/<int:poll_id>/results", views.PollDetailApiView.as_view(), name="polls-results"),
    path("polls/<int:poll_id>/vote", views.PollVoteApiView.as_view(), name="polls-vote"),
    path("archive/pictures/years", views.ArchiveYearsApiView.as_view(), name="archive-years"),
    path("archive/pictures/<int:year>", views.ArchivePicturesByYearApiView.as_view(), name="archive-pictures-by-year"),
    path(
        "archive/pictures/<int:year>/<str:album>",
        views.ArchivePictureDetailApiView.as_view(),
        name="archive-picture-detail",
    ),
    path("archive/documents", views.ArchiveDocumentsApiView.as_view(), name="archive-documents"),
    path("archive/exams", views.ArchiveExamCollectionsApiView.as_view(), name="archive-exams"),
    path("archive/exams/<int:collection_id>", views.ArchiveExamDetailApiView.as_view(), name="archive-exam-detail"),
    path("publications", views.PublicationsListApiView.as_view(), name="publications-list"),
    path("publications/<slug:slug>", views.PublicationsDetailApiView.as_view(), name="publications-detail"),
]
