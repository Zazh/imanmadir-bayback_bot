from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
from django.conf import settings

from .models import BuybackResponse, Buyback


@receiver(post_save, sender=BuybackResponse)
def on_response_status_change(sender, instance, **kwargs):
    """При изменении статуса ответа на шаг"""

    # Только если одобрено модератором (не авто-одобрено)
    if instance.status != BuybackResponse.Status.APPROVED:
        return

    buyback = instance.buyback

    # Проверяем что выкуп ещё в процессе
    if buyback.status != Buyback.Status.IN_PROGRESS:
        return

    # Проверяем что это ответ на текущий шаг
    if instance.step.order != buyback.current_step:
        return

    # Получаем следующий шаг
    next_step = buyback.task.steps.filter(order__gt=buyback.current_step).first()

    # Продвигаем на следующий шаг
    buyback.current_step += 1
    buyback.save(update_fields=['current_step'])

    # Получаем telegram_id пользователя
    chat_id = buyback.user.telegram_id

    if next_step:
        # Формируем сообщение о следующем шаге
        total_steps = buyback.task.steps.count()

        text = f'✅ <b>Модератор одобрил!</b>\n\n'
        text += f'📦 <b>{buyback.task.title}</b>\n'
        text += f'Шаг {next_step.order} из {total_steps}\n\n'

        if next_step.title:
            text += f'<b>{next_step.title}</b>\n\n'

        text += f'{next_step.instruction}\n'

        if next_step.timeout_minutes and not next_step.requires_moderation:
            text += f'\n⏰ Время на выполнение: {next_step.timeout_minutes} мин.'

        # Добавляем подсказку по типу шага
        type_hints = {
            'photo': '\n\n📸 Отправь фото',
            'article_check': '\n\n🔢 Введи артикул товара',
            'text_moderated': '\n\n✏️ Напиши текст',
            'order_number': '\n\n🔢 Введи номер заказа',
            'confirm': '',
            'choice': '',
        }
        text += type_hints.get(next_step.step_type, '')

    else:
        # Все шаги выполнены
        buyback.status = Buyback.Status.ON_REVIEW
        buyback.save(update_fields=['status'])

        text = (
            '🎉 <b>Все шаги выполнены!</b>\n\n'
            'Твой выкуп отправлен на финальную проверку. '
            'Ожидай подтверждения и выплаты.'
        )

    # Отправляем сообщение через Telegram API
    send_telegram_message(chat_id, text)


def send_telegram_message(chat_id: int, text: str):
    """Синхронная отправка сообщения в Telegram"""
    url = f'https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage'

    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f'Ошибка отправки сообщения в Telegram: {e}')