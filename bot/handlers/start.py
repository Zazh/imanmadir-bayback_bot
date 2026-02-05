from telegram import Update
from telegram.ext import ContextTypes
from django.conf import settings

from account.models import TelegramUser
from bot.keyboards.reply import main_menu_keyboard
from bot.keyboards.inline import onboarding_keyboard


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    tg_user = update.effective_user

    user, created = await TelegramUser.objects.aget_or_create(
        telegram_id=tg_user.id,
        defaults={
            'username': tg_user.username or '',
            'first_name': tg_user.first_name or '',
            'last_name': tg_user.last_name or '',
        }
    )

    if not created:
        user.username = tg_user.username or ''
        user.first_name = tg_user.first_name or ''
        user.last_name = tg_user.last_name or ''
        await user.asave(update_fields=['username', 'first_name', 'last_name', 'updated_at'])

    if user.is_blocked:
        await update.message.reply_text('⛔ Ваш аккаунт заблокирован.')
        return

    if not user.is_onboarded:
        welcome_text = (
            f'👋 Привет, {user.display_name}!\n\n'
            f'Этот бот поможет тебе получить товары '
            f'с кешбэком 100% за отзывы.\n\n'
            f'Прежде чем начать, ответь на один вопрос:'
        )
        await update.message.reply_text(welcome_text)

        question_text = (
            '❓ Исключали ли у тебя отзывы на маркетплейсах '
            'за последние 30 дней?'
        )
        await update.message.reply_text(
            question_text,
            reply_markup=onboarding_keyboard(),
        )
        return

    text = f'👋 С возвращением, {user.display_name}!'
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа онбординга"""
    query = update.callback_query
    await query.answer()

    action = query.data.split(':')[1]

    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка. Нажми /start')
        return

    if action == 'excluded':
        user.has_excluded_reviews = True
        user.is_blocked = True
        user.is_onboarded = True
        await user.asave(update_fields=['has_excluded_reviews', 'is_blocked', 'is_onboarded'])

        await query.edit_message_text(
            '😔 К сожалению, мы не можем допустить тебя к заданиям.\n\n'
            f'Если считаешь что это ошибка — напиши @{settings.MANAGER_USERNAME}'
        )
    else:
        user.has_excluded_reviews = False
        user.is_onboarded = True
        await user.asave(update_fields=['has_excluded_reviews', 'is_onboarded'])

        await query.edit_message_text('✅ Отлично! Добро пожаловать!')
        await query.message.reply_text(
            'Выбери действие:',
            reply_markup=main_menu_keyboard(),
        )