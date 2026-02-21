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

class AlumniSignupApiView(APIView, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
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



class AlumniUpdateRequestApiView(APIView, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(operation_id="v1_alumni_update_request_create")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        try:
            from alumni.forms import AlumniEmailVerificationForm
            from alumni.tasks import send_token_email
        except Exception:
            return module_disabled_response("alumni")

        AlumniUpdateToken = self.get_module_models("AlumniUpdateToken")

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



class AlumniUpdateTokenApiView(APIView, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, token):
        token_obj = self._get_valid_token(token)
        if token_obj is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token is invalid or expired."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"data": {"email": token_obj.email, "token": str(token_obj.token), "is_valid": True}})

    @extend_schema(operation_id="v1_alumni_update_token_create")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request, token):
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
        AlumniUpdateToken = self.get_module_models("AlumniUpdateToken")
        token_obj = AlumniUpdateToken.objects.filter(token=token).first()
        if not token_obj:
            return None
        if not token_obj.is_valid():
            return None
        return token_obj
