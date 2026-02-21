from .utils import *

ErrorResponseSchema = inline_serializer(
    name="ApiErrorResponse",
    fields={
        "error": inline_serializer(
            name="ApiErrorDetails",
            fields={
                "code": serializers.CharField(required=False),
                "message": serializers.CharField(required=False),
                "details": serializers.DictField(child=serializers.CharField(), required=False),
            },
        )
    },
)

@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        if request.user.is_authenticated:
            member = request.user
            return Response(
                {
                    "data": {
                        "is_authenticated": True,
                        "username": member.username,
                        "full_name": member.get_full_name(),
                        "email": member.email,
                    }
                }
            )
        return Response({"data": {"is_authenticated": False}})



class LoginApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY, 401: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid username or password."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({"data": {"is_authenticated": True, "username": user.username}})



class LogoutApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request):
        logout(request)
        return Response({"data": {"is_authenticated": False}})



class SignupApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY, 201: OpenApiTypes.ANY, 400: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request):
        form = SignUpForm(request.data)

        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not form.is_valid():
            return Response(
                {"error": {"code": "invalid_form", "message": "Invalid signup data.", "details": form.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = form.save(commit=False)
        user.is_active = False
        user.password = make_password(form.cleaned_data["password"])
        user.save()

        current_site = get_current_site(request)
        message = render_to_string(
            "members/acc_active_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": account_activation_token.make_token(user),
            },
        )
        from core.utils import send_email_task

        to_email = settings.EMAIL_HOST_RECEIVER
        send_email_task.delay(
            "A new account has been created and required your attention.",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
        )
        return Response(
            {"data": {"registered": True, "username": user.username, "requires_activation": True}},
            status=status.HTTP_201_CREATED,
        )



class ActivateApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY, 400: ErrorResponseSchema})
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Member.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Member.DoesNotExist):
            user = None

        if user is not None and account_activation_token.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response({"data": {"activated": True, "username": user.username}})
        return Response(
            {"error": {"code": "invalid_token", "message": "Activation link is invalid."}},
            status=status.HTTP_400_BAD_REQUEST,
        )



class PasswordResetRequestApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(operation_id="v1_auth_password_reset_request")
    @extend_schema(responses={200: OpenApiTypes.ANY, 400: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response(
                {"error": {"code": "invalid_form", "message": "Email is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = Member.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            site_url = settings.CONTENT_VARIABLES.get("SITE_URL", "").rstrip("/")
            reset_url = f"{site_url}/members/reset/{uid}/{token}"
            message = (
                "Du har begärt återställning av lösenord.\n\n"
                f"Följ denna länk för att byta lösenord:\n{reset_url}\n\n"
                "Om du inte begärde detta kan du ignorera meddelandet."
            )
            send_email_task.delay(
                "Password reset request",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        return Response({"data": {"submitted": True}})



class PasswordResetConfirmApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(operation_id="v1_auth_password_reset_confirm")
    @extend_schema(responses={200: OpenApiTypes.ANY, 400: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Member.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Member.DoesNotExist):
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"error": {"code": "invalid_token", "message": "Reset link is invalid."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = SetPasswordForm(
            user=user,
            data={
                "new_password1": request.data.get("new_password1"),
                "new_password2": request.data.get("new_password2"),
            },
        )
        if not form.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid password fields.",
                        "details": form.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.save()
        return Response({"data": {"password_reset": True}})



class PasswordChangeApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.ANY, 400: ErrorResponseSchema}, request=OpenApiTypes.ANY)
    def post(self, request):
        form = PasswordChangeForm(
            user=request.user,
            data={
                "old_password": request.data.get("old_password"),
                "new_password1": request.data.get("new_password1"),
                "new_password2": request.data.get("new_password2"),
            },
        )
        if not form.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid password change fields.",
                        "details": form.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        form.save()
        return Response({"data": {"password_changed": True}})



