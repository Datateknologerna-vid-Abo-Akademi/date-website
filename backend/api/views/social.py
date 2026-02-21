from .utils import *

class AdsListApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "ads"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        AdUrl = self.get_module_models("AdUrl")
        serializer = HomeAdSerializer(AdUrl.objects.all(), many=True)
        return Response({"data": serializer.data})



class SocialOverviewApiView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        social_buttons = settings.CONTENT_VARIABLES.get("SOCIAL_BUTTONS", [])
        harassment_contact_email = settings.CONTENT_VARIABLES.get("ASSOCIATION_EMAIL", "")
        payload = SocialOverviewSerializer(
            {
                "social_buttons": social_buttons,
                "harassment_contact_email": harassment_contact_email,
            }
        ).data
        return Response({"data": payload})



class HarassmentReportApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "social"

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request):
        Harassment, HarassmentEmailRecipient = self.get_module_models("Harassment", "HarassmentEmailRecipient")

        serializer = HarassmentReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_form",
                        "message": "Invalid harassment report fields.",
                        "details": serializer.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not serializer.validated_data.get("consent"):
            return Response(
                {"error": {"code": "consent_required", "message": "Consent is required to submit this form."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not validate_captcha(request.data.get("cf-turnstile-response", "")):
            return Response(
                {"error": {"code": "captcha_failed", "message": "Captcha validation failed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        harassment = Harassment.objects.create(
            email=serializer.validated_data.get("email"),
            message=serializer.validated_data["message"],
        )
        harassment_receivers = list(HarassmentEmailRecipient.objects.values_list("recipient_email", flat=True))
        if harassment_receivers:
            email_ctx = {
                "harassment": harassment,
                "harassment_url": f"{settings.CONTENT_VARIABLES['SITE_URL']}/admin/social/harassment/{harassment.id}",
            }
            send_email_task.delay(
                "Ny trakasserianmälan har inkommit",
                render_to_string("social/harassment_admin_email.html", email_ctx),
                settings.DEFAULT_FROM_EMAIL,
                harassment_receivers,
            )
        return Response({"data": {"submitted": True, "id": harassment.id}}, status=status.HTTP_201_CREATED)



