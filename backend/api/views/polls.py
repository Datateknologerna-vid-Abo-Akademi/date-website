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

class PollListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_polls_retrieve_by_id")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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



