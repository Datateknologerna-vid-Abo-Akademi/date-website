from .utils import *

class LuciaIndexApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "lucia"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Candidate = self.get_module_models("Candidate")

        payload = {
            "title": "Lucia",
            "description": "Lucia candidate presentation and voting portal.",
            "candidate_count": Candidate.objects.filter(published=True).count(),
        }
        return Response({"data": payload})



class LuciaCandidatesApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    module_key = "lucia"

    @extend_schema(operation_id="v1_lucia_candidates_retrieve_list")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Candidate = self.get_module_models("Candidate")

        queryset = Candidate.objects.filter(published=True).order_by("id")
        serializer = LuciaCandidateSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class LuciaCandidateDetailApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    module_key = "lucia"

    @extend_schema(operation_id="v1_lucia_candidates_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, slug):
        Candidate = self.get_module_models("Candidate")

        candidate = Candidate.objects.filter(slug=slug, published=True).first()
        if not candidate:
            return Response(
                {"error": {"code": "not_found", "message": "Lucia candidate not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LuciaCandidateSerializer(candidate)
        return Response({"data": serializer.data})



