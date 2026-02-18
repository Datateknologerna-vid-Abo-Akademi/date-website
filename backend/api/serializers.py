from django.conf import settings
from rest_framework import serializers

from ads.models import AdUrl
from archive.models import Collection, Document, Picture
from events.models import Event
from members.models import Functionary, FunctionaryRole, Member
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
    enabled_modules = serializers.ListField(child=serializers.CharField())


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


class MemberProfileSerializer(serializers.ModelSerializer):
    membership_type = serializers.CharField(source="membership_type.name", read_only=True)
    active_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "address",
            "zip_code",
            "city",
            "country",
            "year_of_admission",
            "membership_type",
            "active_subscription",
        ]
        read_only_fields = ["username", "email", "membership_type", "active_subscription"]

    def get_active_subscription(self, obj):
        subscription = obj.get_active_subscription()
        return subscription.name if subscription else None


class MemberProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["first_name", "last_name", "phone", "address", "zip_code", "city", "country"]


class FunctionaryRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunctionaryRole
        fields = ["id", "title", "board"]


class FunctionarySerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    functionary_role = FunctionaryRoleSerializer(read_only=True)
    functionary_role_id = serializers.PrimaryKeyRelatedField(
        queryset=FunctionaryRole.objects.all(),
        write_only=True,
        source="functionary_role",
        required=False,
    )

    class Meta:
        model = Functionary
        fields = ["id", "year", "member_name", "functionary_role", "functionary_role_id"]

    def get_member_name(self, obj):
        return obj.member.get_full_name()


class PollChoiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    choice_text = serializers.CharField()
    votes = serializers.IntegerField()
    vote_percentage = serializers.SerializerMethodField()

    def get_vote_percentage(self, obj):
        if obj.question.get_total_votes() == 0:
            return 0
        return obj.get_vote_percentage()


class PollQuestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    question_text = serializers.CharField()
    pub_date = serializers.DateTimeField()
    published = serializers.BooleanField()
    show_results = serializers.BooleanField()
    end_vote = serializers.BooleanField()
    multiple_choice = serializers.BooleanField()
    required_multiple_choices = serializers.IntegerField(allow_null=True)
    voting_options = serializers.IntegerField()
    choices = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()

    def get_choices(self, obj):
        queryset = obj.choice_set.order_by("id")
        return PollChoiceSerializer(queryset, many=True).data

    def get_total_votes(self, obj):
        return obj.get_total_votes()


class ArchiveCollectionSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ["id", "title", "type", "pub_date", "hide_for_gulis", "item_count"]

    def get_item_count(self, obj):
        if obj.type == "Pictures":
            return Picture.objects.filter(collection=obj).count()
        return Document.objects.filter(collection=obj).count()


class ArchivePictureSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Picture
        fields = ["id", "image_url", "favorite"]

    def get_image_url(self, obj):
        return obj.image.url


class ArchiveDocumentSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    collection = ArchiveCollectionSerializer(read_only=True)

    class Meta:
        model = Document
        fields = ["id", "title", "document_url", "collection"]

    def get_document_url(self, obj):
        return obj.document.url


class PublicationSerializer(serializers.Serializer):
    title = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    publication_date = serializers.DateField(allow_null=True)
    uploaded_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    is_public = serializers.BooleanField()
    requires_login = serializers.BooleanField()
    pdf_url = serializers.SerializerMethodField()

    def get_pdf_url(self, obj):
        return obj.get_file_url()


class SocialOverviewSerializer(serializers.Serializer):
    social_buttons = serializers.ListField(child=serializers.ListField(child=serializers.CharField()))
    harassment_contact_email = serializers.CharField(allow_blank=True)


class HarassmentReportSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    message = serializers.CharField(max_length=1500)
    consent = serializers.BooleanField(write_only=True)


class CtfListSerializer(serializers.Serializer):
    title = serializers.CharField()
    content = serializers.CharField(allow_blank=True)
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    pub_date = serializers.DateTimeField()
    slug = serializers.CharField()
    published = serializers.BooleanField()
    is_open = serializers.SerializerMethodField()
    is_ended = serializers.SerializerMethodField()

    def get_is_open(self, obj):
        return obj.ctf_is_open()

    def get_is_ended(self, obj):
        return obj.ctf_ended()


class CtfFlagSerializer(serializers.Serializer):
    title = serializers.CharField()
    slug = serializers.CharField()
    clues = serializers.CharField(allow_blank=True)
    solver_name = serializers.SerializerMethodField()
    solved_date = serializers.DateTimeField(allow_null=True)
    is_solved = serializers.SerializerMethodField()

    def get_solver_name(self, obj):
        if not obj.solver:
            return None
        return obj.solver.get_full_name() or obj.solver.username

    def get_is_solved(self, obj):
        return bool(obj.solver)


class LuciaCandidateSerializer(serializers.Serializer):
    img_url = serializers.URLField(allow_blank=True)
    title = serializers.CharField()
    content = serializers.CharField(allow_blank=True)
    published = serializers.BooleanField()
    slug = serializers.CharField()
    poll_url = serializers.URLField(allow_blank=True)
