from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Message
from pipeline.services import send_telegram_message


@receiver(post_save, sender=Message)
def on_message_created(sender, instance, created, **kwargs):
    """При создании сообщения от менеджера — отправляем в Telegram"""

    if not created:
        return

    if instance.sender_type != Message.SenderType.MANAGER:
        return

    chat_id = instance.ticket.user.telegram_id

    text = f'💬 <b>Сообщение от поддержки</b>\n\n{instance.text}'

    send_telegram_message(chat_id, text)