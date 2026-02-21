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

class AdsListApiView(APIView, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "ads"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        AdUrl = self.get_module_models("AdUrl")
        serializer = HomeAdSerializer(AdUrl.objects.all(), many=True)
        return Response({"data": serializer.data})



class SocialOverviewApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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



class HarassmentReportApiView(APIView, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "social"

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        Harassment, HarassmentEmailRecipient = self.get_module_models("Harassment", "HarassmentEmailRecipient")

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



