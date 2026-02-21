from .utils import *

class PublicationsListApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "publications"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        PDFFile = self.get_module_models("PDFFile")

        queryset = PDFFile.objects.filter(is_public=True)
        if not request.user.is_authenticated:
            queryset = queryset.filter(requires_login=False)
        queryset = queryset.order_by("-publication_date")

        page = request.query_params.get("page", 1)
        paginator = Paginator(queryset, 10)
        page_obj = paginator.get_page(page)
        payload = {
            "results": PublicationSerializer(page_obj.object_list, many=True).data,
            "pagination": {
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "total_items": paginator.count,
            },
        }
        return Response({"data": payload})



class PublicationsDetailApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "publications"

    @extend_schema(operation_id="v1_publications_retrieve_by_slug")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, slug):
        PDFFile = self.get_module_models("PDFFile")

        pdf_file = PDFFile.objects.filter(slug=slug).first()
        if not pdf_file:
            return Response(
                {"error": {"code": "not_found", "message": "Publication not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not pdf_file.is_public:
            return Response(
                {"error": {"code": "forbidden", "message": "You do not have permission to access this publication."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        if pdf_file.requires_login and not request.user.is_authenticated:
            return Response(
                {"error": {"code": "unauthenticated", "message": "Login required to access this publication."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = PublicationSerializer(pdf_file)
        return Response({"data": serializer.data})

