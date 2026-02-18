from django.conf import settings
from rest_framework import serializers

from ads.models import AdUrl
from events.models import Event
from news.models import Post
from social.models import IgUrl
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


class StaticUrlSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticUrl
        fields = ["title", "url", "logged_in_only", "dropdown_element"]


class StaticPageNavSerializer(serializers.ModelSerializer):
    urls = serializers.SerializerMethodField()

    class Meta:
        model = StaticPageNav
        fields = ["category_name", "nav_element", "use_category_url", "url", "urls"]

    def get_urls(self, obj):
        urls = StaticUrl.objects.filter(category=obj).order_by("dropdown_element")
        return StaticUrlSerializer(urls, many=True).data


class SiteMetaSerializer(serializers.Serializer):
    project_name = serializers.CharField()
    language_code = serializers.CharField()
    content_variables = serializers.DictField()
    association_theme = serializers.DictField()
    captcha_site_key = serializers.CharField()
    navigation = StaticPageNavSerializer(many=True)
    feature_flags = serializers.ListField(child=serializers.CharField())


class HomeAdSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdUrl
        fields = ["ad_url", "company_url"]


class HomeIgPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgUrl
        fields = ["url", "shortcode"]


class NewsListSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    category_slug = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "content",
            "published_time",
            "author_name",
            "category_name",
            "category_slug",
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name()

    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return None

    def get_category_slug(self, obj):
        if obj.category:
            return obj.category.slug
        return None


class EventListSerializer(serializers.ModelSerializer):
    registration_open_members = serializers.SerializerMethodField()
    registration_open_others = serializers.SerializerMethodField()
    registration_past_due = serializers.SerializerMethodField()
    event_full = serializers.SerializerMethodField()
    sign_up_fields = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "title",
            "slug",
            "content",
            "event_date_start",
            "event_date_end",
            "members_only",
            "sign_up",
            "sign_up_avec",
            "sign_up_max_participants",
            "registration_open_members",
            "registration_open_others",
            "registration_past_due",
            "event_full",
            "redirect_link",
            "image_url",
            "sign_up_fields",
        ]

    def get_registration_open_members(self, obj):
        return obj.registration_is_open_members()

    def get_registration_open_others(self, obj):
        return obj.registration_is_open_others()

    def get_registration_past_due(self, obj):
        return obj.registration_past_due()

    def get_event_full(self, obj):
        return obj.event_is_full()

    def get_sign_up_fields(self, obj):
        fields = obj.get_registration_form()
        if not fields:
            return []
        response = []
        for field in fields:
            response.append(
                {
                    "name": field.name,
                    "type": field.type,
                    "required": field.required,
                    "public_info": field.public_info,
                    "choices": field.get_choices() if field.type == "select" else [],
                    "hide_for_avec": field.hide_for_avec,
                }
            )
        return response

    def get_image_url(self, obj):
        if settings.USE_S3 and obj.s3_image:
            return obj.s3_image.url
        if obj.image:
            return obj.image.url
        return None


class StaticPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticPage
        fields = ["title", "slug", "content", "members_only", "created_time", "modified_time"]
