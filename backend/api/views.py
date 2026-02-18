from itertools import chain

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ads.models import AdUrl
from events.models import Event, EventAttendees
from news.models import Post
from social.models import IgUrl
from staticpages.models import StaticPage, StaticPageNav

from core.utils import validate_captcha
from members.models import Member
from .serializers import (
    EventListSerializer,
    HomeAdSerializer,
    HomeIgPostSerializer,
    NewsListSerializer,
    SiteMetaSerializer,
    StaticPageSerializer,
)


class SiteMetaApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        navigation = StaticPageNav.objects.all().order_by("nav_element")
        payload = {
            "project_name": settings.PROJECT_NAME,
            "language_code": settings.LANGUAGE_CODE,
            "content_variables": settings.CONTENT_VARIABLES,
            "association_theme": settings.ASSOCIATION_THEME,
            "captcha_site_key": settings.CAPTCHA_SITE_KEY,
            "navigation": navigation,
            "feature_flags": settings.EXPERIMENTAL_FEATURES,
        }
        serializer = SiteMetaSerializer(payload)
        return Response({"data": serializer.data})


class HomeApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        events_old_events_included = Event.objects.filter(
            published=True,
            event_date_end__gte=(timezone.now() - timezone.timedelta(days=31)),
        ).order_by("event_date_start")
        events = events_old_events_included.filter(published=True, event_date_end__gte=timezone.now())
        news = Post.objects.filter(published=True, category__isnull=True).order_by("-published_time")[:3]

        aa_posts = Post.objects.filter(
            published=True,
            category__name="Albins Angels",
        ).order_by("-published_time")[:1]
        time_since = timezone.now() - timezone.timedelta(days=10)
        aa_post = aa_posts[0] if aa_posts and aa_posts[0].published_time > time_since else None

        response = {
            "events": EventListSerializer(events, many=True).data,
            "news": NewsListSerializer(news, many=True).data,
            "news_events": self._build_news_events(events, news),
            "ads": HomeAdSerializer(AdUrl.objects.all(), many=True).data,
            "instagram_posts": HomeIgPostSerializer(IgUrl.objects.all(), many=True).data,
            "aa_post": NewsListSerializer(aa_post).data if aa_post else None,
            "calendar_events": self._calendar_format(events_old_events_included),
        }
        return Response({"data": response})

    def _calendar_format(self, events):
        calendar_events_dict = {}
        for event in events:
            event_dict = {
                event.event_date_start.strftime("%Y-%m-%d"): {
                    "link": f"/events/{event.slug}",
                    "modifier": "calendar-eventday",
                    "eventFullDate": event.event_date_start,
                    "eventTitle": event.title,
                }
            }
            calendar_events_dict.update(event_dict)
        return calendar_events_dict

    def _build_news_events(self, events, news):
        merged = []
        for item in chain(events, news):
            if isinstance(item, Event):
                merged.append(
                    {
                        "kind": "event",
                        "title": item.title,
                        "slug": item.slug,
                        "date": item.event_date_start,
                    }
                )
            else:
                merged.append(
                    {
                        "kind": "news",
                        "title": item.title,
                        "slug": item.slug,
                        "date": item.published_time,
                    }
                )
        return merged


class NewsListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category = request.query_params.get("category")
        author = request.query_params.get("author")
        queryset = Post.objects.filter(published=True).order_by("-published_time")

        if category == "none":
            queryset = queryset.filter(category__isnull=True)
        elif category:
            queryset = queryset.filter(category__slug=category)

        if author:
            queryset = queryset.filter(author__username=author)

        serializer = NewsListSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class NewsDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        category = request.query_params.get("category")
        query = Q(slug=slug, published=True)
        if category:
            query &= Q(category__slug=category)
        post = Post.objects.filter(query).first()
        if not post:
            return Response(
                {"error": {"code": "not_found", "message": "News article not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = NewsListSerializer(post)
        return Response({"data": serializer.data})


class EventsListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        include_past = request.query_params.get("include_past", "false").lower() == "true"
        queryset = Event.objects.filter(published=True).order_by("event_date_start")
        if not include_past:
            queryset = queryset.filter(event_date_end__gte=timezone.now())
        serializer = EventListSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class EventDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        event = Event.objects.filter(slug=slug, published=True).first()
        if not event:
            return Response(
                {"error": {"code": "not_found", "message": "Event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if event.members_only and not request.user.is_authenticated:
            return Response(
                {"error": {"code": "forbidden", "message": "You need to login to view this event."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = EventListSerializer(event).data
        payload["passcode_required"] = bool(event.passcode)
        payload["passcode_verified"] = event.passcode == request.session.get("passcode_status", False)
        payload["registration_count"] = event.get_registrations().count()
        payload["registration_public_fields"] = [field.name for field in event.get_registration_form_public_info()]
        return Response({"data": payload})


class EventPasscodeApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, slug):
        event = Event.objects.filter(slug=slug, published=True).first()
        if not event:
            return Response(
                {"error": {"code": "not_found", "message": "Event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not event.passcode:
            return Response(
                {"error": {"code": "invalid_operation", "message": "This event does not require passcode."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        passcode = request.data.get("passcode", "")
        if passcode == event.passcode:
            request.session["passcode_status"] = event.passcode
            return Response({"data": {"passcode_verified": True}})
        return Response(
            {"error": {"code": "invalid_passcode", "message": "Invalid passcode."}},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class EventSignupApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, slug):
        event = Event.objects.filter(slug=slug, published=True).first()
        if not event:
            return Response(
                {"error": {"code": "not_found", "message": "Event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not event.sign_up:
            return Response(
                {"error": {"code": "forbidden", "message": "Signup is disabled for this event."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        if event.passcode and event.passcode != request.session.get("passcode_status", False):
            return Response(
                {"error": {"code": "passcode_required", "message": "Passcode verification required."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_authenticated = request.user.is_authenticated
        member_obj = Member.objects.filter(username=request.user.username).first() if user_authenticated else None
        user_member = member_obj.get_active_subscription() is not None if member_obj else False
        open_for_members = event.registration_is_open_members()
        open_for_others = event.registration_is_open_others()
        commodore_group = request.user.groups.filter(name="commodore").exists() if user_authenticated else False

        if not (
            (user_authenticated and open_for_members and user_member)
            or open_for_others
            or commodore_group
        ):
            return Response(
                {"error": {"code": "forbidden", "message": "Registration is not open for your account."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        form_cls = event.make_registration_form()
        if not form_cls:
            return Response(
                {"error": {"code": "invalid_operation", "message": "Registration form is not available."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event.parent and event.event_is_full():
            return Response(
                {"error": {"code": "event_full", "message": "Event is full."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event.captcha:
            captcha_response = request.data.get("cf-turnstile-response", "")
            if not validate_captcha(captcha_response):
                return Response(
                    {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        form = form_cls(data=request.data)
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid form fields.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_attendee = EventAttendees.objects.filter(email=form.cleaned_data["email"], event=event.id).first()
        attendee = existing_attendee or event.add_event_attendance(
            user=form.cleaned_data["user"],
            email=form.cleaned_data["email"],
            anonymous=form.cleaned_data["anonymous"],
            preferences=form.cleaned_data,
        )
        if "avec" in form.cleaned_data and form.cleaned_data["avec"]:
            self._handle_avec_data(event, form.cleaned_data, attendee)

        return Response(
            {
                "data": {
                    "registered": True,
                    "attendee_email": form.cleaned_data["email"],
                    "event_slug": event.slug,
                }
            },
            status=status.HTTP_201_CREATED,
        )

    def _handle_avec_data(self, event, cleaned_data, attendee):
        avec_data = {"avec_for": attendee}
        for key in cleaned_data:
            if key.startswith("avec_"):
                field_name = key.split("avec_")[1]
                avec_data[field_name] = cleaned_data[key]
        event.add_event_attendance(
            user=avec_data["user"],
            email=avec_data["email"],
            anonymous=avec_data["anonymous"],
            preferences=avec_data,
            avec_for=avec_data["avec_for"],
        )


class StaticPageApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        page = StaticPage.objects.filter(slug=slug).first()
        if not page:
            return Response(
                {"error": {"code": "not_found", "message": "Static page not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        show_content = not page.members_only or (page.members_only and request.user.is_authenticated)
        if not show_content:
            return Response(
                {"error": {"code": "forbidden", "message": "You need to login to view this page."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"data": StaticPageSerializer(page).data})


class SessionApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @ensure_csrf_cookie
    def get(self, request):
        if request.user.is_authenticated:
            member = request.user
            return Response(
                {
                    "data": {
                        "is_authenticated": True,
                        "username": member.username,
                        "full_name": member.get_full_name(),
                        "email": member.email,
                    }
                }
            )
        return Response({"data": {"is_authenticated": False}})


class LoginApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid username or password."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({"data": {"is_authenticated": True, "username": user.username}})


class LogoutApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logout(request)
        return Response({"data": {"is_authenticated": False}})
