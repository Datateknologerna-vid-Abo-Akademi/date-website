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

class EventsListApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: EventListSerializer(many=True)})
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

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        # Keep module-guard patch compatibility with historical api.views namespace.
        from api import views as api_views

        if not api_views.is_module_enabled("events"):
            return api_views.module_disabled_response("events")
        from events.feed import EventFeed

        return EventFeed()(request)



class EventDetailApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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
        payload["template_variant"] = resolve_event_template_variant(event)
        payload["show_attendee_list"] = event.show_attendee_list()
        payload["variant_sections"] = resolve_event_variant_sections(event, request.user)
        return Response({"data": payload})



class EventPasscodeApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
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

        existing_attendee = event.get_registrations().filter(email=form.cleaned_data["email"]).first()
        attendee = existing_attendee or event.add_event_attendance(
            user=form.cleaned_data["user"],
            email=form.cleaned_data["email"],
            anonymous=form.cleaned_data["anonymous"],
            preferences=form.cleaned_data,
        )
        if attendee is not None and "avec" in form.cleaned_data and form.cleaned_data["avec"]:
            self._handle_avec_data(event, form.cleaned_data, attendee)

        billing_payload = self._process_event_billing(event, attendee)
        response_payload = EventSignupResultSerializer(
            {
                "registered": True,
                "attendee_email": form.cleaned_data["email"],
                "event_slug": event.slug,
                "billing": billing_payload,
            }
        ).data
        return Response(
            {"data": response_payload},
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

    def _process_event_billing(self, event, attendee):
        billing_enabled = is_module_enabled("billing") and "event_billing" in settings.EXPERIMENTAL_FEATURES
        payload = {"enabled": billing_enabled, "status": "disabled", "invoice": None}
        if not billing_enabled:
            return payload
        if attendee is None:
            payload["status"] = "already_registered"
            return payload

        EventBillingConfiguration = get_module_model("billing", "EventBillingConfiguration")
        EventInvoice = get_module_model("billing", "EventInvoice")
        if EventBillingConfiguration is None or EventInvoice is None:
            return payload

        signup_event = attendee.original_event or attendee.event or event
        if not EventBillingConfiguration.objects.filter(event=signup_event).exists():
            payload["status"] = "not_configured"
            return payload

        from billing.handlers import handle_event_billing

        try:
            handle_event_billing(attendee)
        except Exception:
            logger.exception("Failed to process event billing for attendee=%s event=%s", attendee.id, event.slug)
            payload["status"] = "processing_error"
            return payload

        invoice = EventInvoice.objects.filter(participant=attendee).order_by("-id").first()
        if invoice is None:
            payload["status"] = "no_invoice_generated"
            return payload

        payload["status"] = "invoice_created"
        payload["invoice"] = EventInvoiceSerializer(invoice).data
        return payload



class EventAttendeesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
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

        public_fields = [field.name for field in event.get_registration_form_public_info()][::-1]
        payload = {
            "template_variant": resolve_event_template_variant(event),
            "show_attendee_list": event.show_attendee_list(),
            "sign_up_max_participants": event.sign_up_max_participants,
            "registration_public_fields": public_fields,
            "attendees": [],
        }
        if event.sign_up and payload["show_attendee_list"]:
            payload["attendees"] = self._serialize_attendees(event, public_fields)

        serializer = EventAttendeeListSerializer(payload)
        return Response({"data": serializer.data})

    def _serialize_attendees(self, event, public_fields):
        attendees = []
        registrations = event.get_registrations()
        for index, attendee in enumerate(registrations, start=1):
            attendees.append(
                {
                    "position": index,
                    "display_name": _("Anonymt") if attendee.anonymous else attendee.user,
                    "anonymous": attendee.anonymous,
                    "is_waitlist": (
                        event.sign_up_max_participants != 0
                        and not event.parent_id
                        and index > event.sign_up_max_participants
                    ),
                    "fields": [
                        {
                            "name": field_name,
                            "value": str(attendee.get_preference(field_name) or ""),
                        }
                        for field_name in public_fields
                    ],
                }
            )
        return attendees



