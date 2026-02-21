from .utils import *

class MemberProfileApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        serializer = MemberProfileSerializer(request.user)
        return Response({"data": serializer.data})

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def patch(self, request):
        serializer = MemberProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid profile data.", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response({"data": MemberProfileSerializer(request.user).data})



class FunctionaryRolesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        queryset = FunctionaryRole.objects.all().order_by("title")
        serializer = FunctionaryRoleSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class PublicFunctionariesApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        queryset = Functionary.objects.select_related("member", "functionary_role").order_by("-year", "functionary_role__title")

        year_param = request.query_params.get("year")
        role_param = request.query_params.get("role")

        if year_param and year_param != "all":
            try:
                queryset = queryset.filter(year=int(year_param))
            except ValueError:
                return Response(
                    {"error": {"code": "invalid_year", "message": "Year must be an integer or 'all'."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if role_param and role_param != "all":
            if role_param.isdigit():
                queryset = queryset.filter(functionary_role__id=int(role_param))
            else:
                queryset = queryset.filter(functionary_role__title=role_param)

        board = queryset.filter(functionary_role__board=True)
        non_board = queryset.filter(functionary_role__board=False)
        response = {
            "board_functionaries_by_role": self._group_by_role(board),
            "functionaries_by_role": self._group_by_role(non_board),
            "distinct_years": list(Functionary.objects.values_list("year", flat=True).distinct().order_by("-year")),
            "roles": FunctionaryRoleSerializer(FunctionaryRole.objects.all().order_by("title"), many=True).data,
        }
        return Response({"data": response})

    def _group_by_role(self, queryset):
        grouped = {}
        for functionary in queryset:
            role_title = functionary.functionary_role.title
            grouped.setdefault(role_title, []).append(FunctionarySerializer(functionary).data)
        return grouped



class MemberFunctionariesApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        queryset = Functionary.objects.filter(member=request.user).select_related("functionary_role", "member").order_by("-year")
        serializer = FunctionarySerializer(queryset, many=True)
        return Response({"data": serializer.data})

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        role_id = request.data.get("functionary_role_id")
        year = request.data.get("year")
        if role_id is None or year is None:
            return Response(
                {"error": {"code": "invalid_form", "message": "Both functionary_role_id and year are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            year = int(year)
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "invalid_year", "message": "Year must be a valid integer."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = FunctionaryRole.objects.filter(id=role_id).first()
        if not role:
            return Response(
                {"error": {"code": "not_found", "message": "Functionary role not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if Functionary.objects.filter(member=request.user, functionary_role=role, year=year).exists():
            return Response(
                {"error": {"code": "duplicate", "message": "Functionary role already exists for this year."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = Functionary.objects.create(member=request.user, functionary_role=role, year=year)
        return Response({"data": FunctionarySerializer(created).data}, status=status.HTTP_201_CREATED)



class MemberFunctionaryDetailApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def delete(self, request, functionary_id):
        functionary = Functionary.objects.filter(id=functionary_id, member=request.user).first()
        if not functionary:
            return Response(
                {"error": {"code": "not_found", "message": "Functionary entry not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        functionary.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



