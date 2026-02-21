from .utils import *

class PollListApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "polls"

    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request):
        Question = self.get_module_models("Question")

        queryset = Question.objects.filter(published=True).order_by("-pub_date")
        serializer = PollQuestionSerializer(queryset, many=True)
        return Response({"data": serializer.data})



class PollDetailApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "polls"

    @extend_schema(operation_id="v1_polls_retrieve_by_id")
    @extend_schema(responses={200: OpenApiTypes.ANY})
    def get(self, request, poll_id):
        Question = self.get_module_models("Question")

        question = Question.objects.filter(id=poll_id, published=True).first()
        if not question:
            return Response(
                {"error": {"code": "not_found", "message": "Poll not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PollQuestionSerializer(question)
        return Response({"data": serializer.data})



class PollVoteApiView(ModuleConfigMixin, APIView):
    permission_classes = [permissions.AllowAny]
    module_key = "polls"

    @extend_schema(responses={200: OpenApiTypes.ANY}, request=OpenApiTypes.ANY)
    def post(self, request, poll_id):
        Question = self.get_module_models("Question")

        question = Question.objects.filter(id=poll_id, published=True).first()
        if not question:
            return Response(
                {"error": {"code": "not_found", "message": "Poll not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        selected_choices = request.data.get("choice_ids", [])
        if not isinstance(selected_choices, list):
            return Response(
                {"error": {"code": "invalid_form", "message": "choice_ids must be a list."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            selected_choices = [int(choice_id) for choice_id in set(selected_choices)]
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "invalid_form", "message": "choice_ids must contain integers."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.is_authenticated:
            user = Member.objects.get(username=request.user.username)
        else:
            user = request.user

        from polls.vote import handle_selected_choices, validate_vote

        error_message = validate_vote(request, question, user, selected_choices)
        if error_message:
            return Response(
                {"error": {"code": "invalid_vote", "message": error_message}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handle_selected_choices(question, selected_choices, user)
        serializer = PollQuestionSerializer(question)
        return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)



