from .utils import *

class CtfModuleMixin(ModuleConfigMixin):
    module_key = "ctf"

    def _get_ctf_models(self):
        return self.get_module_models("Ctf", "Flag", "Guess")

    def _get_ctf_or_404(self, slug):
        Ctf, _, _ = self._get_ctf_models()
        return Ctf.objects.filter(slug=slug, published=True).first()





class CtfListApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(operation_id="v1_ctf_retrieve_list")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Ctf, _, _ = self._get_ctf_models()

        queryset = Ctf.objects.filter(published=True).order_by("-pub_date")[:5]
        serializer = CtfListSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class CtfDetailApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(operation_id="v1_ctf_retrieve_detail")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, slug):
        ctf = self._get_ctf_or_404(slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, _ = self._get_ctf_models()

        flags = Flag.objects.filter(ctf=ctf).order_by("id")
        user_has_solved_any_flag = flags.filter(solver=request.user).exists()
        payload = {
            "ctf": CtfListSerializer(ctf).data,
            "flags": CtfFlagSerializer(flags, many=True).data if ctf.ctf_is_open() else [],
            "user_has_solved_any_flag": user_has_solved_any_flag,
        }
        return Response({"data": payload})



class CtfFlagDetailApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, ctf_slug, flag_slug):
        ctf = self._get_ctf_or_404(ctf_slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, _ = self._get_ctf_models()

        flag = Flag.objects.filter(ctf=ctf, slug=flag_slug).first()
        if not flag:
            return Response(
                {"error": {"code": "not_found", "message": "Flag not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not ctf.ctf_is_open():
            return Response(
                {"error": {"code": "forbidden", "message": "This CTF has not opened yet."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = {
            "ctf": CtfListSerializer(ctf).data,
            "flag": CtfFlagSerializer(flag).data,
            "user_has_solved_any_flag": Flag.objects.filter(ctf=ctf, solver=request.user).exists(),
            "can_submit": ctf.published and ctf.ctf_is_open(),
        }
        return Response({"data": payload})



class CtfFlagGuessApiView(APIView, CtfModuleMixin):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request, ctf_slug, flag_slug):
        ctf = self._get_ctf_or_404(ctf_slug)
        if ctf is None:
            return Response(
                {"error": {"code": "not_found", "message": "CTF event not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, Flag, Guess = self._get_ctf_models()

        flag = Flag.objects.filter(ctf=ctf, slug=flag_slug).first()
        if not flag:
            return Response(
                {"error": {"code": "not_found", "message": "Flag not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not ctf.ctf_is_open() or not ctf.published:
            return Response(
                {"error": {"code": "forbidden", "message": "CTF submissions are not open."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        guess_input = str(request.data.get("guess", "")).strip()
        if not guess_input:
            return Response(
                {"error": {"code": "invalid_form", "message": "A guess is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_has_solved_any_flag = Flag.objects.filter(ctf=ctf, solver=request.user).exists()
        matching_flag = Flag.objects.filter(ctf=ctf, slug=flag_slug, flag=guess_input).first()
        if not matching_flag:
            Guess.objects.create(ctf=ctf, flag=flag, user=request.user, guess=guess_input, correct=False)
            return Response(
                {"error": {"code": "invalid_guess", "message": "Incorrect flag. Please try again."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_solve = not (user_has_solved_any_flag or matching_flag.solver or ctf.ctf_ended())
        if first_solve:
            matching_flag.solver = request.user
            matching_flag.solved_date = timezone.now()
            matching_flag.save(update_fields=["solver", "solved_date"])

        Guess.objects.create(ctf=ctf, flag=matching_flag, user=request.user, guess=guess_input, correct=True)
        payload = {
            "correct": True,
            "first_solve": first_solve,
            "flag": CtfFlagSerializer(matching_flag).data,
        }
        return Response({"data": payload})



