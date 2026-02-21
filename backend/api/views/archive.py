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

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_archive_pictures_retrieve_by_year")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_archive_pictures_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_archive_exams_retrieve_collections")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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

    @extend_schema(operation_id="v1_archive_exams_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
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



