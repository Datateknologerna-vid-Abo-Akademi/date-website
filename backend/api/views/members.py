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

class MemberProfileApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        serializer = MemberProfileSerializer(request.user)
        return Response({"data": serializer.data})

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        queryset = FunctionaryRole.objects.all().order_by("title")
        serializer = FunctionaryRoleSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class PublicFunctionariesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        queryset = Functionary.objects.filter(member=request.user).select_related("functionary_role", "member").order_by("-year")
        serializer = FunctionarySerializer(queryset, many=True)
        return Response({"data": serializer.data})

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def delete(self, request, functionary_id):
        functionary = Functionary.objects.filter(id=functionary_id, member=request.user).first()
        if not functionary:
            return Response(
                {"error": {"code": "not_found", "message": "Functionary entry not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        functionary.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



