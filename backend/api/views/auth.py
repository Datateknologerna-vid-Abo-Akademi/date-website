import logging

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
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiTypes
from rest_framework import serializers

from core.utils import send_email_task, validate_captcha
from members.forms import SignUpForm
from members.models import Functionary, FunctionaryRole, Member, SUPPORTING_MEMBER, FRESHMAN
from members.tokens import account_activation_token
from api.serializers import (
    ArchiveCollectionSerializer,
    ArchiveDocumentSerializer,
    ArchivePictureSerializer,
    CtfFlagSerializer,
    CtfListSerializer,
    EventAttendeeListSerializer,
    EventInvoiceSerializer,
    EventListSerializer,
    EventSignupResultSerializer,
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


logger = logging.getLogger("date")


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

MODULE_CAPABILITY_SPEC = {
    "ads": {
        "label": "Ads",
        "nav_route": "/ads",
        "routes": ["/ads"],
        "features": ["list"],
    },
    "archive": {
        "label": "Archive",
        "nav_route": "/archive",
        "routes": ["/archive", "/archive/pictures", "/archive/documents", "/archive/exams"],
        "features": ["pictures", "documents", "exams"],
    },
    "events": {
        "label": "Events",
        "nav_route": "/events",
        "routes": ["/events", "/events/{slug}", "/events/feed"],
        "features": ["list", "detail", "feed", "passcode", "signup", "attendees", "template_variants"],
    },
    "news": {
        "label": "News",
        "nav_route": "/news",
        "routes": ["/news", "/news/{slug}", "/news/feed"],
        "features": ["list", "detail", "feed", "category_filter", "author_filter"],
    },
    "social": {
        "label": "Social",
        "nav_route": "/social",
        "routes": ["/social", "/social/harassment"],
        "features": ["overview", "harassment_reporting"],
    },
    "staticpages": {
        "label": "Pages",
        "nav_route": "",
        "routes": ["/pages/{slug}"],
        "features": ["navigation", "page_detail"],
    },
    "billing": {
        "label": "Billing",
        "nav_route": "",
        "routes": ["/events/{slug}/signup"],
        "features": ["event_signup_billing"],
    },
    "polls": {
        "label": "Polls",
        "nav_route": "/polls",
        "routes": ["/polls", "/polls/{id}"],
        "features": ["list", "detail", "vote", "results"],
    },
    "publications": {
        "label": "Publications",
        "nav_route": "/publications",
        "routes": ["/publications", "/publications/{slug}"],
        "features": ["list", "detail"],
    },
    "ctf": {
        "label": "CTF",
        "nav_route": "/ctf",
        "routes": ["/ctf", "/ctf/{slug}", "/ctf/{slug}/{flag}"],
        "features": ["list", "detail", "flag_detail", "guess"],
    },
    "lucia": {
        "label": "Lucia",
        "nav_route": "/lucia",
        "routes": ["/lucia", "/lucia/candidates", "/lucia/candidates/{slug}"],
        "features": ["overview", "candidates", "candidate_detail"],
    },
    "alumni": {
        "label": "Alumni",
        "nav_route": "/alumni",
        "routes": ["/alumni", "/alumni/signup", "/alumni/update", "/alumni/update/{token}"],
        "features": ["signup", "update_request", "update_token"],
    },
}



from .utils import *
@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        logout(request)
        return Response({"data": {"is_authenticated": False}})



class SignupApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_auth_password_reset_request")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(operation_id="v1_auth_password_reset_confirm")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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



