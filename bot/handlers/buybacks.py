from telegram import Update
from telegram.ext import ContextTypes

from account.models import TelegramUser
from tasks.models import Buyback
from bot.keyboards.inline import buyback_detail_keyboard


async def my_buybacks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список выкупов пользователя"""
    user_id = update.effective_user.id

    try:
        user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Профиль не найден. Нажми /start')
        return

    buybacks = []
    async for bb in Buyback.objects.filter(user=user).select_related('task').order_by('-started_at')[:10]:
        buybacks.append(bb)

    if not buybacks:
        await update.message.reply_text(
            '📦 <b>Мои выкупы</b>\n\n'
            'У тебя пока нет выкупов. Выбери задание в меню!',
            parse_mode='HTML'
        )
        return

    text = '📦 <b>Мои выкупы</b>\n\n'

    status_emoji = {
        Buyback.Status.IN_PROGRESS: '🔄',
        Buyback.Status.ON_REVIEW: '⏳',
        Buyback.Status.COMPLETED: '✅',
        Buyback.Status.PAID: '💰',
        Buyback.Status.CANCELLED: '❌',
        Buyback.Status.EXPIRED: '⏰',
    }

    for bb in buybacks:
        emoji = status_emoji.get(bb.status, '❓')
        text += f'{emoji} {bb.task.title}\n'
        text += f'    Статус: {bb.get_status_display()}\n'
        text += f'    Шаг: {bb.current_step}\n\n'

    await update.message.reply_text(text, parse_mode='HTML')