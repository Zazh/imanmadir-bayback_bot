from telegram import Update
from telegram.ext import ContextTypes
from django.conf import settings

from account.models import TelegramUser
from bot.keyboards.reply import main_menu_keyboard


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Профиль не найден. Нажми /start')
        return

    # Реквизиты
    if user.has_payment_info:
        payment_info = f'{user.bank_name}: {user.phone}\n👤 {user.card_holder_name}'
    else:
        payment_info = 'Не указаны'

    text = (
        f'👤 <b>Твой профиль</b>\n\n'
        f'<b>ID:</b> <code>{user.telegram_id}</code>\n'
        f'<b>Имя:</b> {user.display_name}\n\n'
        f'💳 <b>Реквизиты:</b>\n{payment_info}\n\n'
        f'📊 <b>Выполнено выкупов:</b> {user.total_completed}\n'
        f'📅 <b>Дата регистрации:</b> {user.created_at.strftime("%d.%m.%Y")}'
    )

    await update.message.reply_text(text, parse_mode='HTML')


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    text = (
        '❓ <b>Помощь</b>\n\n'
        '<b>Как это работает:</b>\n'
        '1. Выбери задание из списка\n'
        '2. Выполняй шаги по инструкции\n'
        '3. Получи выплату\n\n'
        f'<b>Вопросы?</b> Напиши @{settings.MANAGER_USERNAME}'
    )
    await update.message.reply_text(text, parse_mode='HTML')