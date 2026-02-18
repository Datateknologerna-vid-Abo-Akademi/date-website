from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import send_email_task, validate_captcha
from members.forms import SignUpForm
from members.models import Functionary, FunctionaryRole, Member, SUPPORTING_MEMBER, FRESHMAN
from members.tokens import account_activation_token
from .serializers import (
    ArchiveCollectionSerializer,
    ArchiveDocumentSerializer,
    ArchivePictureSerializer,
    CtfFlagSerializer,
    CtfListSerializer,
    EventListSerializer,
    FunctionaryRoleSerializer,
    FunctionarySerializer,
    HarassmentReportSerializer,
    HomeAdSerializer,
    HomeIgPostSerializer,
    LuciaCandidateSerializer,
    MemberProfileSerializer,
    MemberProfileUpdateSerializer,
    NewsListSerializer,
    PollQuestionSerializer,
    PublicationSerializer,
    SiteMetaSerializer,
    SocialOverviewSerializer,
    StaticPageSerializer,
)


MODULE_APP_MAP = {
    "ads": "ads",
    "archive": "archive",
    "events": "events",
    "news": "news",
    "social": "social",
    "staticpages": "staticpages",
    "billing": "billing",
    "polls": "polls",
    "publications": "publications",
    "ctf": "ctf",
    "lucia": "lucia",
    "alumni": "alumni",
}


def is_module_enabled(module_key):
    app_label = MODULE_APP_MAP.get(module_key)
    return app_label is not None and apps.is_installed(app_label)


def module_disabled_response(module_key):
    return Response(
        {
            "error": {
                "code": "feature_disabled",
                "message": f"The '{module_key}' module is not enabled for this association.",
            }
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def get_optional_model(app_label, model_name):
    if not apps.is_installed(app_label):
        return None
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def get_module_model(module_key, model_name):
    app_label = MODULE_APP_MAP.get(module_key, module_key)
    return get_optional_model(app_label, model_name)


class SiteMetaApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        navigation = self._build_navigation()
        payload = {
            "project_name": settings.PROJECT_NAME,
            "language_code": settings.LANGUAGE_CODE,
            "content_variables": settings.CONTENT_VARIABLES,
            "association_theme": settings.ASSOCIATION_THEME,
            "captcha_site_key": settings.CAPTCHA_SITE_KEY,
            "navigation": navigation,
            "feature_flags": settings.EXPERIMENTAL_FEATURES,
            "enabled_modules": sorted([key for key in MODULE_APP_MAP if is_module_enabled(key)]),
            "default_landing_path": getattr(settings, "FRONTEND_DEFAULT_ROUTE", "/"),
        }
        serializer = SiteMetaSerializer(payload)
        return Response({"data": serializer.data})

    def _build_navigation(self):
        if not is_module_enabled("staticpages"):
            return []
        StaticPageNav = get_module_model("staticpages", "StaticPageNav")
        StaticUrl = get_module_model("staticpages", "StaticUrl")
        if StaticPageNav is None or StaticUrl is None:
            return []

        navigation = []
        for nav_category in StaticPageNav.objects.all().order_by("nav_element"):
            urls = [
                {
                    "title": url.title,
                    "url": url.url,
                    "logged_in_only": url.logged_in_only,
                    "dropdown_element": url.dropdown_element,
                }
                for url in StaticUrl.objects.filter(category=nav_category).order_by("dropdown_element")
            ]
            navigation.append(
                {
                    "category_name": nav_category.category_name,
                    "nav_element": nav_category.nav_element,
                    "use_category_url": nav_category.use_category_url,
                    "url": nav_category.url,
                    "urls": urls,
                }
            )
        return navigation


class HomeApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Event = get_module_model("events", "Event")
        Post = get_module_model("news", "Post")
        AdUrl = get_module_model("ads", "AdUrl")
        IgUrl = get_module_model("social", "IgUrl")

        events_old_events_included = (
            Event.objects.filter(
                published=True,
                event_date_end__gte=(timezone.now() - timezone.timedelta(days=31)),
            ).order_by("event_date_start")
            if Event is not None
            else []
        )
        events = (
            events_old_events_included.filter(published=True, event_date_end__gte=timezone.now())
            if Event is not None
            else []
        )
        news = (
            Post.objects.filter(published=True, category__isnull=True).order_by("-published_time")[:3]
            if Post is not None
            else []
        )

        if Post is not None:
            aa_posts = Post.objects.filter(
                published=True,
                category__name="Albins Angels",
            ).order_by("-published_time")[:1]
            time_since = timezone.now() - timezone.timedelta(days=10)
            aa_post = aa_posts[0] if aa_posts and aa_posts[0].published_time > time_since else None
        else:
            aa_post = None

        response = {
            "events": EventListSerializer(events, many=True).data,
            "news": NewsListSerializer(news, many=True).data,
            "news_events": self._build_news_events(events, news),
            "ads": HomeAdSerializer(AdUrl.objects.all(), many=True).data if AdUrl is not None else [],
            "instagram_posts": HomeIgPostSerializer(IgUrl.objects.all(), many=True).data if IgUrl is not None else [],
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
        for item in events:
            merged.append(
                {
                    "kind": "event",
                    "title": item.title,
                    "slug": item.slug,
                    "date": item.event_date_start,
                }
            )
        for item in news:
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
        Post = get_module_model("news", "Post")
        if Post is None:
            return Response({"data": []})

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


class NewsFeedApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not is_module_enabled("news"):
            return module_disabled_response("news")
        from news.feed import LatestPosts

        return LatestPosts()(request)


class NewsDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        Post = get_module_model("news", "Post")
        if Post is None:
            return module_disabled_response("news")

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
        Event = get_module_model("events", "Event")
        if Event is None:
            return Response({"data": []})

        include_past = request.query_params.get("include_past", "false").lower() == "true"
        queryset = Event.objects.filter(published=True).order_by("event_date_start")
        if not include_past:
            queryset = queryset.filter(event_date_end__gte=timezone.now())
        serializer = EventListSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class EventsFeedApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not is_module_enabled("events"):
            return module_disabled_response("events")
        from events.feed import EventFeed

        return EventFeed()(request)


class EventDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        Event = get_module_model("events", "Event")
        if Event is None:
            return module_disabled_response("events")

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
        Event = get_module_model("events", "Event")
        if Event is None:
            return module_disabled_response("events")

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
        Event = get_module_model("events", "Event")
        EventAttendees = get_module_model("events", "EventAttendees")
        if Event is None or EventAttendees is None:
            return module_disabled_response("events")

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
        StaticPage = get_module_model("staticpages", "StaticPage")
        if StaticPage is None:
            return module_disabled_response("staticpages")

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


class SocialOverviewApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        social_buttons = settings.CONTENT_VARIABLES.get("SOCIAL_BUTTONS", [])
        harassment_contact_email = settings.CONTENT_VARIABLES.get("ASSOCIATION_EMAIL", "")
        payload = SocialOverviewSerializer(
            {
                "social_buttons": social_buttons,
                "harassment_contact_email": harassment_contact_email,
            }
        ).data
        return Response({"data": payload})


class AdsListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        AdUrl = get_module_model("ads", "AdUrl")
        if AdUrl is None:
            return Response({"data": []})
        serializer = HomeAdSerializer(AdUrl.objects.all(), many=True)
        return Response({"data": serializer.data})


class HarassmentReportApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        Harassment = get_module_model("social", "Harassment")
        HarassmentEmailRecipient = get_module_model("social", "HarassmentEmailRecipient")
        if Harassment is None or HarassmentEmailRecipient is None:
            return module_disabled_response("social")

        serializer = HarassmentReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid harassment report fields.",
                        "details": serializer.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not serializer.validated_data.get("consent"):
            return Response(
                {"error": {"code": "consent_required", "message": "Consent is required to submit this form."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        harassment = Harassment.objects.create(
            email=serializer.validated_data.get("email"),
            message=serializer.validated_data["message"],
        )
        harassment_receivers = list(HarassmentEmailRecipient.objects.values_list("recipient_email", flat=True))
        if harassment_receivers:
            email_ctx = {
                "harassment": harassment,
                "harassment_url": f"{settings.CONTENT_VARIABLES['SITE_URL']}/admin/social/harassment/{harassment.id}",
            }
            send_email_task.delay(
                "Ny trakasserianmälan har inkommit",
                render_to_string("social/harassment_admin_email.html", email_ctx),
                settings.DEFAULT_FROM_EMAIL,
                harassment_receivers,
            )
        return Response({"data": {"submitted": True, "id": harassment.id}}, status=status.HTTP_201_CREATED)


class CtfModuleMixin:
    def _get_ctf_models(self):
        if not is_module_enabled("ctf"):
            return None, None, None
        return (
            get_optional_model("ctf", "Ctf"),
            get_optional_model("ctf", "Flag"),
            get_optional_model("ctf", "Guess"),
        )

    def _get_ctf_or_404(self, slug):
        Ctf, _, _ = self._get_ctf_models()
        if Ctf is None:
            return None
        return Ctf.objects.filter(slug=slug, published=True).first()


class CtfListApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        Ctf, _, _ = self._get_ctf_models()
        if Ctf is None:
            return module_disabled_response("ctf")

        queryset = Ctf.objects.filter(published=True).order_by("-pub_date")[:5]
        serializer = CtfListSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class CtfDetailApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        ctf = self._get_ctf_or_404(slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, _ = self._get_ctf_models()
        if Flag is None:
            return module_disabled_response("ctf")

        flags = Flag.objects.filter(ctf=ctf).order_by("id")
        user_has_solved_any_flag = flags.filter(solver=request.user).exists()
        payload = {
            "ctf": CtfListSerializer(ctf).data,
            "flags": CtfFlagSerializer(flags, many=True).data if ctf.ctf_is_open() else [],
            "user_has_solved_any_flag": user_has_solved_any_flag,
        }
        return Response({"data": payload})


class CtfFlagDetailApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ctf_slug, flag_slug):
        ctf = self._get_ctf_or_404(ctf_slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, _ = self._get_ctf_models()
        if Flag is None:
            return module_disabled_response("ctf")

        flag = Flag.objects.filter(ctf=ctf, slug=flag_slug).first()
        if not flag:
            return Response(
                {"error": {"code": "not_found", "message": "Flag not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not ctf.ctf_is_open():
            return Response(
                {"error": {"code": "forbidden", "message": "This CTF has not opened yet."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = {
            "ctf": CtfListSerializer(ctf).data,
            "flag": CtfFlagSerializer(flag).data,
            "user_has_solved_any_flag": Flag.objects.filter(ctf=ctf, solver=request.user).exists(),
            "can_submit": ctf.published and ctf.ctf_is_open(),
        }
        return Response({"data": payload})


class CtfFlagGuessApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ctf_slug, flag_slug):
        ctf = self._get_ctf_or_404(ctf_slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, Guess = self._get_ctf_models()
        if Flag is None or Guess is None:
            return module_disabled_response("ctf")

        flag = Flag.objects.filter(ctf=ctf, slug=flag_slug).first()
        if not flag:
            return Response(
                {"error": {"code": "not_found", "message": "Flag not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not ctf.ctf_is_open() or not ctf.published:
            return Response(
                {"error": {"code": "forbidden", "message": "CTF submissions are not open."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        guess_input = str(request.data.get("guess", "")).strip()
        if not guess_input:
            return Response(
                {"error": {"code": "invalid_form", "message": "A guess is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_has_solved_any_flag = Flag.objects.filter(ctf=ctf, solver=request.user).exists()
        matching_flag = Flag.objects.filter(ctf=ctf, slug=flag_slug, flag=guess_input).first()
        if not matching_flag:
            Guess.objects.create(ctf=ctf, flag=flag, user=request.user, guess=guess_input, correct=False)
            return Response(
                {"error": {"code": "invalid_guess", "message": "Incorrect flag. Please try again."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_solve = not (user_has_solved_any_flag or matching_flag.solver or ctf.ctf_ended())
        if first_solve:
            matching_flag.solver = request.user
            matching_flag.solved_date = timezone.now()
            matching_flag.save(update_fields=["solver", "solved_date"])

        Guess.objects.create(ctf=ctf, flag=matching_flag, user=request.user, guess=guess_input, correct=True)
        payload = {
            "correct": True,
            "first_solve": first_solve,
            "flag": CtfFlagSerializer(matching_flag).data,
        }
        return Response({"data": payload})


class LuciaIndexApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not is_module_enabled("lucia"):
            return module_disabled_response("lucia")
        Candidate = get_optional_model("lucia", "Candidate")
        if Candidate is None:
            return module_disabled_response("lucia")

        payload = {
            "title": "Lucia",
            "description": "Lucia candidate presentation and voting portal.",
            "candidate_count": Candidate.objects.filter(published=True).count(),
        }
        return Response({"data": payload})


class LuciaCandidatesApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_module_enabled("lucia"):
            return module_disabled_response("lucia")
        Candidate = get_optional_model("lucia", "Candidate")
        if Candidate is None:
            return module_disabled_response("lucia")

        queryset = Candidate.objects.filter(published=True).order_by("id")
        serializer = LuciaCandidateSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class LuciaCandidateDetailApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        if not is_module_enabled("lucia"):
            return module_disabled_response("lucia")
        Candidate = get_optional_model("lucia", "Candidate")
        if Candidate is None:
            return module_disabled_response("lucia")

        candidate = Candidate.objects.filter(slug=slug, published=True).first()
        if not candidate:
            return Response(
                {"error": {"code": "not_found", "message": "Lucia candidate not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LuciaCandidateSerializer(candidate)
        return Response({"data": serializer.data})


class AlumniSignupApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not is_module_enabled("alumni"):
            return module_disabled_response("alumni")
        try:
            from alumni.forms import AlumniSignUpForm
            from alumni.gsuite_adapter import DateSheetsAdapter
            from alumni.tasks import AUTH, MEMBER_SHEET_NAME, SHEET, handle_alumni_signup
        except Exception:
            return module_disabled_response("alumni")

        form = AlumniSignUpForm(request.data)
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid alumni signup data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._email_already_registered(form.cleaned_data["email"], DateSheetsAdapter, AUTH, SHEET, MEMBER_SHEET_NAME):
            return Response(
                {"error": {"code": "duplicate_email", "message": "Email already registered."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_alumni_signup.delay(form.cleaned_data)
        return Response({"data": {"submitted": True, "operation": "CREATE"}}, status=status.HTTP_201_CREATED)

    def _email_already_registered(self, email, adapter_cls, auth, sheet_key, worksheet_name):
        if not auth or not sheet_key:
            return False
        try:
            client = adapter_cls(auth, sheet_key, worksheet_name)
            emails = client.get_column_values(client.get_column_by_name("email"))
            return email in emails
        except Exception:
            return False


class AlumniUpdateRequestApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not is_module_enabled("alumni"):
            return module_disabled_response("alumni")
        try:
            from alumni.forms import AlumniEmailVerificationForm
            from alumni.tasks import send_token_email
        except Exception:
            return module_disabled_response("alumni")

        AlumniUpdateToken = get_optional_model("alumni", "AlumniUpdateToken")
        if AlumniUpdateToken is None:
            return module_disabled_response("alumni")

        form = AlumniEmailVerificationForm(request.data)
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid email.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = AlumniUpdateToken(email=form.cleaned_data["email"])
        token.save()
        send_token_email.delay(str(token.token), form.cleaned_data["email"])
        return Response({"data": {"submitted": True}}, status=status.HTTP_201_CREATED)


class AlumniUpdateTokenApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        token_obj = self._get_valid_token(token)
        if token_obj is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token is invalid or expired."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"data": {"email": token_obj.email, "token": str(token_obj.token), "is_valid": True}})

    def post(self, request, token):
        if not is_module_enabled("alumni"):
            return module_disabled_response("alumni")
        try:
            from alumni.forms import AlumniUpdateForm
            from alumni.tasks import handle_alumni_signup
        except Exception:
            return module_disabled_response("alumni")

        token_obj = self._get_valid_token(token)
        if token_obj is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token is invalid or expired."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        form_data = request.data.copy()
        form_data["email"] = token_obj.email
        form_data["token"] = str(token_obj.token)
        form_data["operation"] = "UPDATE"

        form = AlumniUpdateForm(form_data, initial={"email": token_obj.email, "token": token_obj.token})
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid alumni update data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_alumni_signup.delay(form.cleaned_data, timezone.now())
        return Response({"data": {"updated": True}}, status=status.HTTP_201_CREATED)

    def _get_valid_token(self, token):
        if not is_module_enabled("alumni"):
            return None
        AlumniUpdateToken = get_optional_model("alumni", "AlumniUpdateToken")
        if AlumniUpdateToken is None:
            return None
        token_obj = AlumniUpdateToken.objects.filter(token=token).first()
        if not token_obj:
            return None
        if not token_obj.is_valid():
            return None
        return token_obj


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


class SignupApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        form = SignUpForm(request.data)

        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid signup data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = form.save(commit=False)
        user.is_active = False
        user.password = make_password(form.cleaned_data["password"])
        user.save()

        current_site = get_current_site(request)
        message = render_to_string(
            "members/acc_active_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": account_activation_token.make_token(user),
            },
        )
        from core.utils import send_email_task

        to_email = settings.EMAIL_HOST_RECEIVER
        send_email_task.delay(
            "A new account has been created and required your attention.",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
        )
        return Response(
            {"data": {"registered": True, "username": user.username, "requires_activation": True}},
            status=status.HTTP_201_CREATED,
        )


class ActivateApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Member.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Member.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response({"data": {"activated": True, "username": user.username}})
        return Response(
            {"error": {"code": "invalid_token", "message": "Activation link is invalid."}},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PasswordResetRequestApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response(
                {"error": {"code": "invalid_form", "message": "Email is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = Member.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            site_url = settings.CONTENT_VARIABLES.get("SITE_URL", "").rstrip("/")
            reset_url = f"{site_url}/members/reset/{uid}/{token}"
            message = (
                "Du har begärt återställning av lösenord.\n\n"
                f"Följ denna länk för att byta lösenord:\n{reset_url}\n\n"
                "Om du inte begärde detta kan du ignorera meddelandet."
            )
            send_email_task.delay(
                "Password reset request",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        return Response({"data": {"submitted": True}})


class PasswordResetConfirmApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Member.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Member.DoesNotExist):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"error": {"code": "invalid_token", "message": "Reset link is invalid."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = SetPasswordForm(
            user=user,
            data={
                "new_password1": request.data.get("new_password1"),
                "new_password2": request.data.get("new_password2"),
            },
        )
        if not form.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid password fields.",
                        "details": form.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.save()
        return Response({"data": {"password_reset": True}})


class PasswordChangeApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        form = PasswordChangeForm(
            user=request.user,
            data={
                "old_password": request.data.get("old_password"),
                "new_password1": request.data.get("new_password1"),
                "new_password2": request.data.get("new_password2"),
            },
        )
        if not form.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid password change fields.",
                        "details": form.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.save()
        return Response({"data": {"password_changed": True}})


class MemberProfileApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = MemberProfileSerializer(request.user)
        return Response({"data": serializer.data})

    def patch(self, request):
        serializer = MemberProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid profile data.", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response({"data": MemberProfileSerializer(request.user).data})


class FunctionaryRolesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = FunctionaryRole.objects.all().order_by("title")
        serializer = FunctionaryRoleSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class PublicFunctionariesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Functionary.objects.select_related("member", "functionary_role").order_by("-year", "functionary_role__title")

        year_param = request.query_params.get("year")
        role_param = request.query_params.get("role")

        if year_param and year_param != "all":
            try:
                queryset = queryset.filter(year=int(year_param))
            except ValueError:
                return Response(
                    {"error": {"code": "invalid_year", "message": "Year must be an integer or 'all'."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if role_param and role_param != "all":
            if role_param.isdigit():
                queryset = queryset.filter(functionary_role__id=int(role_param))
            else:
                queryset = queryset.filter(functionary_role__title=role_param)

        board = queryset.filter(functionary_role__board=True)
        non_board = queryset.filter(functionary_role__board=False)
        response = {
            "board_functionaries_by_role": self._group_by_role(board),
            "functionaries_by_role": self._group_by_role(non_board),
            "distinct_years": list(Functionary.objects.values_list("year", flat=True).distinct().order_by("-year")),
            "roles": FunctionaryRoleSerializer(FunctionaryRole.objects.all().order_by("title"), many=True).data,
        }
        return Response({"data": response})

    def _group_by_role(self, queryset):
        grouped = {}
        for functionary in queryset:
            role_title = functionary.functionary_role.title
            grouped.setdefault(role_title, []).append(FunctionarySerializer(functionary).data)
        return grouped


class MemberFunctionariesApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Functionary.objects.filter(member=request.user).select_related("functionary_role", "member").order_by("-year")
        serializer = FunctionarySerializer(queryset, many=True)
        return Response({"data": serializer.data})

    def post(self, request):
        role_id = request.data.get("functionary_role_id")
        year = request.data.get("year")
        if role_id is None or year is None:
            return Response(
                {"error": {"code": "invalid_form", "message": "Both functionary_role_id and year are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            year = int(year)
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "invalid_year", "message": "Year must be a valid integer."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = FunctionaryRole.objects.filter(id=role_id).first()
        if not role:
            return Response(
                {"error": {"code": "not_found", "message": "Functionary role not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if Functionary.objects.filter(member=request.user, functionary_role=role, year=year).exists():
            return Response(
                {"error": {"code": "duplicate", "message": "Functionary role already exists for this year."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = Functionary.objects.create(member=request.user, functionary_role=role, year=year)
        return Response({"data": FunctionarySerializer(created).data}, status=status.HTTP_201_CREATED)


class MemberFunctionaryDetailApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, functionary_id):
        functionary = Functionary.objects.filter(id=functionary_id, member=request.user).first()
        if not functionary:
            return Response(
                {"error": {"code": "not_found", "message": "Functionary entry not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        functionary.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PollListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not is_module_enabled("polls"):
            return Response({"data": []})

        Question = get_optional_model("polls", "Question")
        if Question is None:
            return Response({"data": []})

        queryset = Question.objects.filter(published=True).order_by("-pub_date")
        serializer = PollQuestionSerializer(queryset, many=True)
        return Response({"data": serializer.data})


class PollDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, poll_id):
        if not is_module_enabled("polls"):
            return module_disabled_response("polls")

        Question = get_optional_model("polls", "Question")
        if Question is None:
            return module_disabled_response("polls")

        question = Question.objects.filter(id=poll_id, published=True).first()
        if not question:
            return Response(
                {"error": {"code": "not_found", "message": "Poll not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PollQuestionSerializer(question)
        return Response({"data": serializer.data})


class PollVoteApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, poll_id):
        if not is_module_enabled("polls"):
            return module_disabled_response("polls")

        Question = get_optional_model("polls", "Question")
        if Question is None:
            return module_disabled_response("polls")

        question = Question.objects.filter(id=poll_id, published=True).first()
        if not question:
            return Response(
                {"error": {"code": "not_found", "message": "Poll not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        selected_choices = request.data.get("choice_ids", [])
        if not isinstance(selected_choices, list):
            return Response(
                {"error": {"code": "invalid_form", "message": "choice_ids must be a list."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            selected_choices = [int(choice_id) for choice_id in set(selected_choices)]
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "invalid_form", "message": "choice_ids must contain integers."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.is_authenticated:
            user = Member.objects.get(username=request.user.username)
        else:
            user = request.user

        from polls.vote import handle_selected_choices, validate_vote

        error_message = validate_vote(request, question, user, selected_choices)
        if error_message:
            return Response(
                {"error": {"code": "invalid_vote", "message": error_message}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_selected_choices(question, selected_choices, user)
        serializer = PollQuestionSerializer(question)
        return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)


class ArchiveAccessMixin:
    def check_archive_access(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": {"code": "unauthenticated", "message": "Login required."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if request.user.membership_type.permission_profile == SUPPORTING_MEMBER:
            return Response(
                {"error": {"code": "forbidden", "message": "Access denied for this membership type."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def serialize_paginated(self, queryset, serializer_cls, page, page_size):
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        return {
            "results": serializer_cls(page_obj.object_list, many=True).data,
            "pagination": {
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "total_items": paginator.count,
            },
        }


class ArchiveYearsApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Collection = get_module_model("archive", "Collection")
        if Collection is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        years = Collection.objects.dates("pub_date", "year").reverse()
        year_albumcount = {}
        for year in years:
            year_albumcount[str(year.year)] = Collection.objects.filter(
                pub_date__year=year.year,
                type="Pictures",
            ).count()
        return Response({"data": {"year_albums": year_albumcount}})


class ArchivePicturesByYearApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request, year):
        Collection = get_module_model("archive", "Collection")
        if Collection is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collections = Collection.objects.filter(type="Pictures", pub_date__year=year).order_by("-pub_date")
        return Response({"data": ArchiveCollectionSerializer(collections, many=True).data})


class ArchivePictureCollectionByIdApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request, collection_id):
        Collection = get_module_model("archive", "Collection")
        if Collection is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collection = Collection.objects.filter(pk=collection_id, type="Pictures").first()
        if not collection:
            return Response(
                {"error": {"code": "not_found", "message": "Picture collection not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = {
            "collection": ArchiveCollectionSerializer(collection).data,
            "year": collection.pub_date.year,
            "album": collection.title,
        }
        return Response({"data": payload})


class ArchivePictureDetailApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request, year, album):
        Collection = get_module_model("archive", "Collection")
        Picture = get_module_model("archive", "Picture")
        if Collection is None or Picture is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collection = Collection.objects.filter(type="Pictures", pub_date__year=year, title=album).order_by("-pub_date").first()
        if not collection:
            return Response(
                {"error": {"code": "not_found", "message": "Picture collection not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if collection.hide_for_gulis and request.user.membership_type.permission_profile == FRESHMAN:
            return Response(
                {"error": {"code": "forbidden", "message": "This collection is not available for freshmen."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        pictures = (
            Picture.objects.filter(collection=collection)
            if year == 2022
            else Picture.objects.filter(collection=collection).reverse()
        )
        page = request.query_params.get("page", 1)
        payload = self.serialize_paginated(pictures, ArchivePictureSerializer, page, 15)
        payload["collection"] = ArchiveCollectionSerializer(collection).data
        return Response({"data": payload})


class ArchiveDocumentsApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Collection = get_module_model("archive", "Collection")
        Document = get_module_model("archive", "Document")
        if Collection is None or Document is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        filter_collection = request.query_params.get("collection", "")
        filter_title_contains = request.query_params.get("title_contains", "")
        page = request.query_params.get("page", 1)

        queryset = Document.objects.filter(collection__type="Documents")
        if filter_collection:
            queryset = queryset.filter(collection=filter_collection)
        if filter_title_contains:
            queryset = queryset.filter(title__contains=filter_title_contains)

        payload = self.serialize_paginated(queryset, ArchiveDocumentSerializer, page, 15)
        payload["collections"] = ArchiveCollectionSerializer(
            Collection.objects.filter(type="Documents").order_by("title"),
            many=True,
        ).data
        return Response({"data": payload})


class ArchiveExamCollectionsApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Collection = get_module_model("archive", "Collection")
        if Collection is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collections = Collection.objects.filter(type="Exams").order_by("title")
        return Response({"data": ArchiveCollectionSerializer(collections, many=True).data})


class ArchiveExamDetailApiView(APIView, ArchiveAccessMixin):
    permission_classes = [permissions.AllowAny]

    def get(self, request, collection_id):
        Collection = get_module_model("archive", "Collection")
        Document = get_module_model("archive", "Document")
        if Collection is None or Document is None:
            return module_disabled_response("archive")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collection = Collection.objects.filter(pk=collection_id, type="Exams").first()
        if not collection:
            return Response(
                {"error": {"code": "not_found", "message": "Exam collection not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        queryset = Document.objects.filter(collection=collection_id)
        page = request.query_params.get("page", 1)
        payload = self.serialize_paginated(queryset, ArchiveDocumentSerializer, page, 15)
        payload["collection"] = ArchiveCollectionSerializer(collection).data
        return Response({"data": payload})


class PublicationsListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not is_module_enabled("publications"):
            return Response({"data": {"results": [], "pagination": {"page": 1, "num_pages": 1, "has_next": False, "has_previous": False, "total_items": 0}}})

        PDFFile = get_optional_model("publications", "PDFFile")
        if PDFFile is None:
            return module_disabled_response("publications")

        queryset = PDFFile.objects.filter(is_public=True)
        if not request.user.is_authenticated:
            queryset = queryset.filter(requires_login=False)
        queryset = queryset.order_by("-publication_date")

        page = request.query_params.get("page", 1)
        payload = ArchiveAccessMixin().serialize_paginated(queryset, PublicationSerializer, page, 10)
        return Response({"data": payload})


class PublicationsDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        if not is_module_enabled("publications"):
            return module_disabled_response("publications")

        PDFFile = get_optional_model("publications", "PDFFile")
        if PDFFile is None:
            return module_disabled_response("publications")

        pdf_file = PDFFile.objects.filter(slug=slug).first()
        if not pdf_file:
            return Response(
                {"error": {"code": "not_found", "message": "Publication not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not pdf_file.is_public:
            return Response(
                {"error": {"code": "forbidden", "message": "You do not have permission to access this publication."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        if pdf_file.requires_login and not request.user.is_authenticated:
            return Response(
                {"error": {"code": "unauthenticated", "message": "Login required to access this publication."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = PublicationSerializer(pdf_file)
        return Response({"data": serializer.data})
