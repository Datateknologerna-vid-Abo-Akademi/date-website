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


def is_module_enabled(module_key):
    app_label = MODULE_APP_MAP.get(module_key)
    return app_label is not None and apps.is_installed(app_label)


def build_module_capabilities():
    capabilities = {}
    event_billing_enabled = is_module_enabled("billing") and "event_billing" in settings.EXPERIMENTAL_FEATURES
    for module_key in MODULE_APP_MAP:
        spec = MODULE_CAPABILITY_SPEC.get(module_key, {"label": module_key.title(), "nav_route": "", "routes": [], "features": []})
        enabled = is_module_enabled(module_key)
        features = list(spec["features"])

        if module_key == "events":
            if event_billing_enabled:
                features.append("billing_status")
        if module_key == "billing" and not event_billing_enabled:
            features = []

        capabilities[module_key] = {
            "enabled": enabled,
            "label": spec["label"],
            "nav_route": spec["nav_route"],
            "routes": spec["routes"],
            "features": features if enabled else [],
        }
    return capabilities


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


class ModuleConfigMixin:
    """
    A DRY abstraction for Django Rest Framework API views that belong to specific optional modules.
    Set the `module_key` class variable to automatically enforce the `is_module_enabled` check 
    upon dispatch, preventing boilerplate feature checks across the system.
    """
    module_key = None

    def dispatch(self, request, *args, **kwargs):
        if self.module_key and not is_module_enabled(self.module_key):
            return module_disabled_response(self.module_key)
        return super().dispatch(request, *args, **kwargs)
        
    def get_module_models(self, *model_names):
        """Returns a single model or a tuple of models for the view's configured module."""
        if not self.module_key:
            raise ValueError("ModuleConfigMixin requires `module_key` to be set on the class to fetch models.")
        models = [get_module_model(self.module_key, name) for name in model_names]
        if len(models) == 1:
            return models[0]
        return tuple(models)


EVENT_TEMPLATE_VARIANTS_BY_TITLE = {
    "årsfest": "arsfest",
    "årsfest 2026": "arsfest",
    "årsfest gäster": "arsfest",
    "100 baal": "kk100",
    "baal": "baal",
    "tomtejakt": "tomtejakt",
    "wappmiddag": "wappmiddag",
}

EVENT_TEMPLATE_VARIANTS_BY_SLUG = {
    "baal": "baal",
    "tomtejakt": "tomtejakt",
    "wappmiddag": "wappmiddag",
    "arsfest": "arsfest",
    "arsfest_stipendiater": "arsfest",
    "arsfest26": "arsfest",
    "on100_main": "arsfest",
    "on100_student": "arsfest",
    "on100_alumn": "arsfest",
    "on100_guest": "arsfest",
    "on100_secret": "arsfest",
    "on100_stippe": "arsfest",
}


def resolve_event_template_variant(event):
    title_key = event.title.lower().strip()
    if title_key in EVENT_TEMPLATE_VARIANTS_BY_TITLE:
        return EVENT_TEMPLATE_VARIANTS_BY_TITLE[title_key]
    if event.slug in EVENT_TEMPLATE_VARIANTS_BY_SLUG:
        return EVENT_TEMPLATE_VARIANTS_BY_SLUG[event.slug]
    return "default"


def resolve_event_variant_sections(event, user):
    variant = resolve_event_template_variant(event)
    if variant == "default":
        return []

    if not is_module_enabled("staticpages"):
        return []

    StaticPage = get_module_model("staticpages", "StaticPage")
    if StaticPage is None:
        return []

    # Event landing variants can optionally reference static pages by using
    # slug prefixes tied to the event slug, e.g. "baal-program".
    prefix_patterns = [f"{event.slug}-", f"{event.slug}_"]
    slug_filter = Q()
    for prefix in prefix_patterns:
        slug_filter |= Q(slug__startswith=prefix)

    queryset = StaticPage.objects.filter(slug_filter).order_by("title")
    if not user.is_authenticated:
        queryset = queryset.filter(members_only=False)

    sections = []
    for page in queryset:
        clean_slug = page.slug
        for prefix in prefix_patterns:
            if clean_slug.startswith(prefix):
                clean_slug = clean_slug[len(prefix):]
                break
        if not clean_slug:
            clean_slug = page.slug
        sections.append(
            {
                "slug": clean_slug,
                "title": page.title,
                "content": page.content,
            }
        )
    return sections


