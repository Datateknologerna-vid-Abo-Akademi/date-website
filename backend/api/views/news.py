from .utils import *

class NewsListApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "news"

    @extend_schema(operation_id="v1_news_retrieve_list")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Post = self.get_module_models("Post")
        if Post is None:
            return Response({"data": []})

        category = request.query_params.get("category")
        author = request.query_params.get("author")
        queryset = Post.objects.filter(published=True).order_by("-published_time")

        if category == "none":
            queryset = queryset.filter(category__isnull=True)
        elif category:
            queryset = queryset.filter(category__slug=category)

        if author:
            queryset = queryset.filter(author__username=author)

        serializer = NewsListSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class NewsFeedApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "news"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        from news.feed import LatestPosts

        return LatestPosts()(request)



class NewsDetailApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "news"

    @extend_schema(operation_id="v1_news_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, slug):
        Post = self.get_module_models("Post")

        category = request.query_params.get("category")
        query = Q(slug=slug, published=True)
        if category:
            query &= Q(category__slug=category)
        post = Post.objects.filter(query).first()
        if not post:
            return Response(
                {"error": {"code": "not_found", "message": "News article not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = NewsListSerializer(post)
        return Response({"data": serializer.data})



