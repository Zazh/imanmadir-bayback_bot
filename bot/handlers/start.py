from telegram import Update
from telegram.ext import ContextTypes
from django.conf import settings
from account.models import TelegramUser
from bot.keyboards.reply import main_menu_keyboard
from bot.keyboards.inline import onboarding_keyboard

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    tg_user = update.effective_user

    # Получаем или создаём пользователя
    user, created = await TelegramUser.objects.aget_or_create(
        telegram_id=tg_user.id,
        defaults={
            'username': tg_user.username or '',
            'first_name': tg_user.first_name or '',
            'last_name': tg_user.last_name or '',
        }
    )

    # Обновляем данные если пользователь уже существует
    if not created:
        user.username = tg_user.username or ''
        user.first_name = tg_user.first_name or ''
        user.last_name = tg_user.last_name or ''
        await user.asave(update_fields=['username', 'first_name', 'last_name', 'updated_at'])

    # Проверяем блокировку
    if user.is_blocked:
        await update.message.reply_text('⛔ Ваш аккаунт заблокирован.')
        return

    # Если не прошёл онбординг — показываем приветствие и вопрос
    if not user.is_onboarded:
        welcome_text = (
            f'👋 Привет, {user.display_name}!\n\n'
            f'Бот дает возможность получить наши товары '
            f'с кешбэком 100% за ответы на вопросы.\n\n'
            f'Продолжая использовать бот, вы соглашаетесь с нашими документами.\n\n'
            f'📋 <a href="{settings.DOCUMENTS_URL}">Документы для ознакомления</a>\n\n'
            f'Приятных покупок ❤️\n\n'
            f'P.S. Если что-то не понятно — напишите @{settings.MANAGER_USERNAME} '
            f'и ждите ответа оператора.'
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

        # Вопрос об отзывах
        question_text = (
            '❓ Для начала уточним: исключали ли у вас отзывы '
            'на маркетплейсах за последние 30 дней?\n\n'
            'Пожалуйста, отвечайте честно.\n\n'
            '<i>P.S. Если у нас появятся сомнения, то можем '
            'выборочно запросить скриншот ваших отзывов</i>'
        )
        await update.message.reply_text(
            question_text,
            parse_mode='HTML',
            reply_markup=onboarding_keyboard(),
        )
        return

    # Если уже прошёл онбординг — просто приветствие
    text = f'👋 С возвращением, {user.display_name}! Выберите в меню себе задание!'
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на вопрос онбординга"""
    query = update.callback_query
    await query.answer()

    action = query.data.split(':')[1]  # excluded или not_excluded

    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка. Нажми /start')
        return

    if action == 'excluded':
        # Отзывы исключали
        user.has_excluded_reviews = True
        user.is_onboarded = True
        await user.asave(update_fields=['has_excluded_reviews', 'is_onboarded', 'updated_at'])

        await query.edit_message_text(
            '⚠️ К сожалению, мы не можем допустить вас к заданиям, '
            'так как есть риск исключения отзывов.\n\n'
            f'Если считаете, что это ошибка — напишите @{settings.MANAGER_USERNAME}'
        )

        # Блокируем пользователя
        user.is_blocked = True
        await user.asave(update_fields=['is_blocked'])

    else:
        # Отзывы не исключали
        user.has_excluded_reviews = False
        user.is_onboarded = True
        await user.asave(update_fields=['has_excluded_reviews', 'is_onboarded', 'updated_at'])

        await query.edit_message_text('✅ Отлично! Добро пожаловать!')

        # Показываем меню
        await query.message.reply_text(
            'Выбери действие:',
            reply_markup=main_menu_keyboard(),
        )