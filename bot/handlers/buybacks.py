from telegram import Update
from telegram.ext import ContextTypes

from account.models import TelegramUser
from pipeline.models import Buyback


async def my_buybacks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои выкупы"""
    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Нажми /start')
        return

    buybacks = []
    async for bb in Buyback.objects.filter(user=user).select_related('task').order_by('-started_at')[:10]:
        buybacks.append(bb)

    if not buybacks:
        await update.message.reply_text(
            '📦 <b>Мои выкупы</b>\n\n'
            'У тебя пока нет выкупов.',
            parse_mode='HTML'
        )
        return

    status_emoji = {
        Buyback.Status.IN_PROGRESS: '🔄',
        Buyback.Status.ON_MODERATION: '⏳',
        Buyback.Status.PENDING_REVIEW: '📝',
        Buyback.Status.APPROVED: '✅',
        Buyback.Status.REJECTED: '❌',
        Buyback.Status.CANCELLED: '🚫',
        Buyback.Status.EXPIRED: '⏰',
    }

    text = '📦 <b>Мои выкупы</b>\n\n'
    for bb in buybacks:
        emoji = status_emoji.get(bb.status, '❓')
        text += f'{emoji} {bb.task.title}\n'
        text += f'    Статус: {bb.get_status_display()}\n\n'

    await update.message.reply_text(text, parse_mode='HTML')