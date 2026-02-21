from .utils import *

class AlumniSignupApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        try:
            from alumni.forms import AlumniSignUpForm
            from alumni.gsuite_adapter import DateSheetsAdapter
            from alumni.tasks import AUTH, MEMBER_SHEET_NAME, SHEET, handle_alumni_signup
        except Exception:
            return module_disabled_response("alumni")

        form = AlumniSignUpForm(request.data)
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid alumni signup data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._email_already_registered(form.cleaned_data["email"], DateSheetsAdapter, AUTH, SHEET, MEMBER_SHEET_NAME):
            return Response(
                {"error": {"code": "duplicate_email", "message": "Email already registered."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_alumni_signup.delay(form.cleaned_data)
        return Response({"data": {"submitted": True, "operation": "CREATE"}}, status=status.HTTP_201_CREATED)

    def _email_already_registered(self, email, adapter_cls, auth, sheet_key, worksheet_name):
        if not auth or not sheet_key:
            return False
        try:
            client = adapter_cls(auth, sheet_key, worksheet_name)
            emails = client.get_column_values(client.get_column_by_name("email"))
            return email in emails
        except Exception:
            return False



class AlumniUpdateRequestApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(operation_id="v1_alumni_update_request_create")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        try:
            from alumni.forms import AlumniEmailVerificationForm
            from alumni.tasks import send_token_email
        except Exception:
            return module_disabled_response("alumni")

        AlumniUpdateToken = self.get_module_models("AlumniUpdateToken")

        form = AlumniEmailVerificationForm(request.data)
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid email.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = AlumniUpdateToken(email=form.cleaned_data["email"])
        token.save()
        send_token_email.delay(str(token.token), form.cleaned_data["email"])
        return Response({"data": {"submitted": True}}, status=status.HTTP_201_CREATED)



class AlumniUpdateTokenApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "alumni"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, token):
        token_obj = self._get_valid_token(token)
        if token_obj is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token is invalid or expired."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"data": {"email": token_obj.email, "token": str(token_obj.token), "is_valid": True}})

    @extend_schema(operation_id="v1_alumni_update_token_create")
    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request, token):
        try:
            from alumni.forms import AlumniUpdateForm
            from alumni.tasks import handle_alumni_signup
        except Exception:
            return module_disabled_response("alumni")

        token_obj = self._get_valid_token(token)
        if token_obj is None:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token is invalid or expired."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        form_data = request.data.copy()
        form_data["email"] = token_obj.email
        form_data["token"] = str(token_obj.token)
        form_data["operation"] = "UPDATE"

        form = AlumniUpdateForm(form_data, initial={"email": token_obj.email, "token": token_obj.token})
        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid alumni update data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_alumni_signup.delay(form.cleaned_data, timezone.now())
        return Response({"data": {"updated": True}}, status=status.HTTP_201_CREATED)

    def _get_valid_token(self, token):
        AlumniUpdateToken = self.get_module_models("AlumniUpdateToken")
        token_obj = AlumniUpdateToken.objects.filter(token=token).first()
        if not token_obj:
            return None
        if not token_obj.is_valid():
            return None
        return token_obj
