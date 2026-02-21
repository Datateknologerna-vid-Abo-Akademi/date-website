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





class ArchiveYearsApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Collection = self.get_module_models("Collection")

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



class ArchivePicturesByYearApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(operation_id="v1_archive_pictures_retrieve_by_year")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, year):
        Collection = self.get_module_models("Collection")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collections = Collection.objects.filter(type="Pictures", pub_date__year=year).order_by("-pub_date")
        return Response({"data": ArchiveCollectionSerializer(collections, many=True).data})



class ArchivePictureCollectionByIdApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, collection_id):
        Collection = self.get_module_models("Collection")

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



class ArchivePictureDetailApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(operation_id="v1_archive_pictures_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, year, album):
        Collection, Picture = self.get_module_models("Collection", "Picture")

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



class ArchiveDocumentsApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Collection, Document = self.get_module_models("Collection", "Document")

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



class ArchiveExamCollectionsApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(operation_id="v1_archive_exams_retrieve_collections")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Collection = self.get_module_models("Collection")

        auth_error = self.check_archive_access(request)
        if auth_error:
            return auth_error

        collections = Collection.objects.filter(type="Exams").order_by("title")
        return Response({"data": ArchiveCollectionSerializer(collections, many=True).data})



class ArchiveExamDetailApiView(APIView, ArchiveAccessMixin, ModuleConfigMixin):
    permission_classes = [permissions.AllowAny]
    module_key = "archive"

    @extend_schema(operation_id="v1_archive_exams_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, collection_id):
        Collection, Document = self.get_module_models("Collection", "Document")

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



