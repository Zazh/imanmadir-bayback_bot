from django.conf import settings
import requests

from steps.models import StepType


def format_step_message(task, step, total_steps: int, prefix: str = '') -> str:
    """Форматирование сообщения шага"""
    text = prefix
    text += f'📦 <b>{task.title}</b>\n'
    text += f'Шаг {step.order} из {total_steps}\n\n'

    if step.title:
        text += f'<b>{step.title}</b>\n\n'

    text += step.instruction

    # Подсказки по типу шага
    hints = {
        StepType.PHOTO: '\n\n📸 Отправь фото',
        StepType.ARTICLE_CHECK: '\n\n🔢 Введи артикул товара',
        StepType.TEXT_MODERATED: '\n\n✏️ Напиши текст',
        StepType.ORDER_NUMBER: '\n\n🔢 Введи номер заказа',
        StepType.CHECK_LINK: '\n\n🔗 Отправь ссылку',
        StepType.CONFIRM: '',
        StepType.CHOICE: '',
        StepType.PAYMENT_DETAILS: '\n\n💳 Введи номер телефона:',
    }
    text += hints.get(step.step_type, '')

    return text


def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None):
    """Отправка сообщения в Telegram"""
    url = f'https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage'

    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
    }

    if reply_markup:
        import json
        data['reply_markup'] = json.dumps(reply_markup)

    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f'Telegram send error: {e}')