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

    @extend_schema(operation_id="v1_ctf_retrieve_list")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Ctf, _, _ = self._get_ctf_models()
        if Ctf is None:
            return module_disabled_response("ctf")

        queryset = Ctf.objects.filter(published=True).order_by("-pub_date")[:5]
        serializer = CtfListSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class CtfDetailApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(operation_id="v1_ctf_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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



