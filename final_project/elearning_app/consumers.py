import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import *

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_pk = self.scope["url_route"]["kwargs"]["chat_pk"]
        self.chat_group_name = f"chat_{self.chat_pk}"
        
        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name,
        )

    async def receive(self, text_data=None):
        data = json.loads(text_data)
        message = data["message"]
        user_pk = data["user_pk"]
        chat_pk = data["chat_pk"]

        # Check that user is a participant
        is_participant = await self.is_user_participant(user_pk, chat_pk)
        if not is_participant:
            await self.send(text_data=json.dumps({
                "error": "User is not a participant of this chat. Cannot send message."
            }))
            return

        # Save message to database to keep history
        await self.save_message(message, user_pk, chat_pk)

        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender_id": user_pk
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender_id": event["sender_id"]
        }))

    @database_sync_to_async
    def save_message(self, message, user_pk, chat_pk):
        ChatMessage.objects.create(
            chat_id=chat_pk,
            sender_id=user_pk,
            text=message
        )

    @database_sync_to_async
    def is_user_participant(self, user_pk, chat_pk):
        return ChatParticipant.objects.filter(chat_id=chat_pk, user_id=user_pk).exists()
