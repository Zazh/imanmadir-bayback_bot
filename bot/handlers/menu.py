from telegram import Update
from telegram.ext import ContextTypes
from django.conf import settings

from account.models import TelegramUser
from bot.keyboards.reply import main_menu_keyboard
from bot.keyboards.inline import profile_keyboard


async def get_user(telegram_id: int) -> TelegramUser | None:
    """Получить пользователя из БД"""
    try:
        return await TelegramUser.objects.aget(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки Помощь"""
    text = (
        '❓ <b>Помощь</b>\n\n'
        'Это бот для выполнения заданий по выкупу товаров.\n\n'
        '<b>Как это работает:</b>\n'
        '1. Выбери задание из списка\n'
        '2. Выполняй шаги по инструкции\n'
        '3. Получи вознаграждение\n\n'
        f'<b>Возникли вопросы?</b>\n'
        f'Напиши менеджеру: @{settings.MANAGER_USERNAME}'
    )
    await update.message.reply_text(text, parse_mode='HTML')


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки Профиль"""
    user = await get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text('⚠️ Профиль не найден. Нажми /start')
        return

    card_display = user.card_number if user.card_number else 'не указан'
    phone_display = user.phone if user.phone else 'не указан'

    text = (
        '👤 <b>Твой профиль</b>\n\n'
        f'<b>ID:</b> <code>{user.telegram_id}</code>\n'
        f'<b>Имя:</b> {user.display_name}\n\n'
        f'💳 <b>Номер карты:</b> {card_display}\n'
        f'📱 <b>Телефон:</b> {phone_display}\n\n'
        f'📊 <b>Выполнено выкупов:</b> {user.total_completed}\n'
        f'📅 <b>Дата регистрации:</b> {user.created_at.strftime("%d.%m.%Y")}'
    )

    await update.message.reply_text(text, parse_mode='HTML', reply_markup=profile_keyboard())