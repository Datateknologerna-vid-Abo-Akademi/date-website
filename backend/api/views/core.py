from .utils import *

class SiteMetaApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: SiteMetaSerializer})
    def get(self, request):
        navigation = self._build_navigation()
        module_capabilities = build_module_capabilities()
        payload = {
            "project_name": settings.PROJECT_NAME,
            "language_code": settings.LANGUAGE_CODE,
            "content_variables": settings.CONTENT_VARIABLES,
            "association_theme": settings.ASSOCIATION_THEME,
            "captcha_site_key": settings.CAPTCHA_SITE_KEY,
            "navigation": navigation,
            "feature_flags": settings.EXPERIMENTAL_FEATURES,
            "enabled_modules": sorted([key for key, value in module_capabilities.items() if value["enabled"]]),
            "module_capabilities": module_capabilities,
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

    @extend_schema(
        responses={
            200: inline_serializer(
                name="HomeResponse",
                fields={
                    "events": EventListSerializer(many=True),
                    "news": NewsListSerializer(many=True),
                    "news_events": serializers.ListField(child=serializers.DictField()),
                    "ads": HomeAdSerializer(many=True),
                    "instagram_posts": HomeIgPostSerializer(many=True),
                    "aa_post": NewsListSerializer(allow_null=True),
                    "calendar_events": serializers.DictField(),
                }
            )
        }
    )
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



class StaticPageApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "staticpages"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, slug):
        StaticPage = self.get_module_models("StaticPage")

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



