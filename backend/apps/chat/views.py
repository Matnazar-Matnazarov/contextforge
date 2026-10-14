from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ServiceError
from apps.organizations.permissions import OrgContextMixin

from . import services
from .models import Conversation, Message
from .serializers import AskSerializer, ConversationSerializer, MessageSerializer


class _ConvScoped(OrgContextMixin):
    def get_conversation(self, conversation_id) -> Conversation:
        # Owner AND organization both come from the server-side context. Others' conversations are 404.
        conv = Conversation.objects.filter(
            pk=conversation_id, organization=self.organization, owner=self.membership.user
        ).first()
        if conv is None:
            raise ServiceError("Conversation not found.", code="not_found", status_code=404)
        return conv


class ConversationListCreateView(_ConvScoped, ListAPIView):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(organization=self.organization, owner=self.membership.user)

    @extend_schema(request=ConversationSerializer, responses={201: ConversationSerializer})
    def post(self, request, org_id):
        serializer = ConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conv = services.create_conversation(
            membership=self.membership, title=serializer.validated_data.get("title", "")
        )
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(_ConvScoped, APIView):
    @extend_schema(responses=ConversationSerializer)
    def get(self, request, org_id, conversation_id):
        return Response(ConversationSerializer(self.get_conversation(conversation_id)).data)

    @extend_schema(responses={204: None})
    def delete(self, request, org_id, conversation_id):
        self.get_conversation(conversation_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListCreateView(_ConvScoped, APIView):
    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "chat"
        return super().get_throttles()

    @extend_schema(responses=MessageSerializer(many=True))
    def get(self, request, org_id, conversation_id):
        conv = self.get_conversation(conversation_id)
        qs = Message.objects.filter(conversation=conv).prefetch_related("citations")
        return Response(MessageSerializer(qs, many=True).data)

    @extend_schema(request=AskSerializer, responses={201: MessageSerializer})
    def post(self, request, org_id, conversation_id):
        conv = self.get_conversation(conversation_id)
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_msg, assistant = services.ask(
            membership=self.membership, conversation=conv, question=serializer.validated_data["question"]
        )
        return Response(
            {"user_message": MessageSerializer(user_msg).data, "assistant_message": MessageSerializer(assistant).data},
            status=status.HTTP_201_CREATED,
        )
