from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from account.models import TelegramUser
from tasks.models import Task, TaskStep, Buyback, BuybackResponse
from bot.states import BuybackState
from bot.keyboards.reply import main_menu_keyboard

# Состояния ConversationHandler
STEP_RESPONSE = 1

# Время напоминания в секундах (2 минуты)
REMINDER_DELAY = 120


async def get_user(telegram_id: int) -> TelegramUser | None:
    try:
        return await TelegramUser.objects.aget(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return None


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминания пользователю"""
    job = context.job
    buyback_id = job.data['buyback_id']
    chat_id = job.data['chat_id']

    try:
        buyback = await Buyback.objects.select_related('task__product').aget(id=buyback_id)
    except Buyback.DoesNotExist:
        return

    # Проверяем что выкуп всё ещё в процессе
    if buyback.status != Buyback.Status.IN_PROGRESS:
        return

    product = buyback.task.product
    available = await product.aget_quantity_available()
    total = product.quantity_total

    text = (
        f'💝 Напоминание!\n\n'
        f'Ты взял задание "{buyback.task.title}", но пока не продолжил.\n\n'
        f'Товаров по акции осталось: {available}/{total}\n\n'
        f'Продолжи выполнение или отмени задание, чтобы освободить место для других.'
    )

    await context.bot.send_message(chat_id=chat_id, text=text)


def schedule_reminder(context: ContextTypes.DEFAULT_TYPE, buyback_id: int, chat_id: int):
    """Запланировать напоминание"""
    if not context.job_queue:
        return  # JobQueue недоступен (webhook режим)

    job_name = f'reminder_{buyback_id}'
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_once(
        send_reminder,
        when=REMINDER_DELAY,
        data={'buyback_id': buyback_id, 'chat_id': chat_id},
        name=job_name,
    )


def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, buyback_id: int):
    """Отменить напоминание"""
    if not context.job_queue:
        return  # JobQueue недоступен (webhook режим)

    job_name = f'reminder_{buyback_id}'
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()


def get_step_keyboard(step: TaskStep, buyback_id: int):
    """Клавиатура для шага"""
    buttons = []

    if step.step_type == TaskStep.StepType.CONFIRM:
        buttons.append([InlineKeyboardButton('✅ Готово', callback_data=f'step_confirm:{buyback_id}')])

    elif step.step_type == TaskStep.StepType.CHOICE:
        choices = step.settings.get('choices', [])
        for choice in choices:
            buttons.append([InlineKeyboardButton(choice, callback_data=f'step_choice:{buyback_id}:{choice}')])

    buttons.append([InlineKeyboardButton('❌ Отменить выкуп', callback_data=f'cancel_buyback:{buyback_id}')])

    return InlineKeyboardMarkup(buttons)


async def show_current_step(update: Update, context: ContextTypes.DEFAULT_TYPE, buyback: Buyback):
    """Показать текущий шаг"""
    step = await buyback.task.steps.filter(order=buyback.current_step).afirst()

    if not step:
        buyback.status = Buyback.Status.ON_REVIEW
        await buyback.asave(update_fields=['status'])

        cancel_reminder(context, buyback.id)

        text = (
            '🎉 <b>Все шаги выполнены!</b>\n\n'
            'Твой выкуп отправлен на проверку. '
            'Ожидай подтверждения и выплаты.'
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode='HTML')
        else:
            await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_menu_keyboard())

        return ConversationHandler.END

    task = await Task.objects.select_related('product').aget(id=buyback.task_id)
    total_steps = await task.steps.acount()

    text = (
        f'📦 <b>{task.title}</b>\n'
        f'Шаг {step.order} из {total_steps}\n\n'
        f'📝 <b>Инструкция:</b>\n{step.instruction}\n'
    )

    if step.step_type == TaskStep.StepType.PHOTO:
        text += '\n📸 Отправь фото'
    elif step.step_type == TaskStep.StepType.ARTICLE_CHECK:
        text += '\n🔢 Введи артикул товара'
    elif step.step_type == TaskStep.StepType.TEXT_MODERATED:
        hint = step.settings.get('hint', '')
        if hint:
            text += f'\n💡 Подсказка: {hint}'
        text += '\n✏️ Напиши текст'
    elif step.step_type == TaskStep.StepType.ORDER_NUMBER:
        text += '\n🔢 Введи номер заказа'

    if step.timeout_hours:
        text += f'\n\n⏰ Время на выполнение: {step.timeout_hours} ч.'

    context.user_data['buyback_id'] = buyback.id
    context.user_data['step_id'] = step.id
    context.user_data['step_type'] = step.step_type

    keyboard = get_step_keyboard(step, buyback.id)

    chat_id = update.effective_chat.id
    schedule_reminder(context, buyback.id, chat_id)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

    return STEP_RESPONSE


async def take_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Взять задание"""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(':')[1])
    user = await get_user(update.effective_user.id)

    if not user:
        await query.edit_message_text('⚠️ Профиль не найден. Нажми /start')
        return ConversationHandler.END

    if user.is_blocked:
        await query.edit_message_text('⛔ Ваш аккаунт заблокирован.')
        return ConversationHandler.END

    try:
        task = await Task.objects.select_related('product').aget(id=task_id, is_active=True)
    except Task.DoesNotExist:
        await query.edit_message_text('⚠️ Задание не найдено или неактивно')
        return ConversationHandler.END

    # Проверяем доступность товара
    available = await task.product.aget_quantity_available()
    if available <= 0:
        await query.edit_message_text('⚠️ Товар закончился')
        return ConversationHandler.END

    # Проверяем лимит пользователя
    from bot.handlers.tasks import check_user_limit
    can_take, limit_msg = await check_user_limit(user, task.product)
    if not can_take:
        await query.edit_message_text(f'⚠️ Лимит исчерпан: {limit_msg}')
        return ConversationHandler.END

    # Проверяем нет ли уже активного выкупа
    has_active = await Buyback.objects.filter(
        task=task,
        user=user,
        status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
    ).aexists()

    if has_active:
        await query.edit_message_text('⚠️ У тебя уже есть активный выкуп этого задания')
        return ConversationHandler.END

    # Создаём выкуп
    buyback = await Buyback.objects.acreate(
        task=task,
        user=user,
        current_step=1,
        status=Buyback.Status.IN_PROGRESS,
    )

    # Показываем сколько осталось (уже с учётом нового выкупа)
    new_available = await task.product.aget_quantity_available()
    total = task.product.quantity_total

    await query.edit_message_text(
        f'✅ Задание взято!\n\n'
        f'💝 Товаров по акции осталось: {new_available}/{total}\n\n'
        f'Загружаю первый шаг...'
    )

    return await show_current_step(update, context, buyback)


async def handle_step_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на шаг (фото, текст)"""
    buyback_id = context.user_data.get('buyback_id')
    step_id = context.user_data.get('step_id')
    step_type = context.user_data.get('step_type')

    if not buyback_id or not step_id:
        await update.message.reply_text('⚠️ Ошибка. Начни заново через меню.')
        return ConversationHandler.END

    try:
        buyback = await Buyback.objects.select_related('task', 'user').aget(id=buyback_id)
        step = await TaskStep.objects.aget(id=step_id)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        await update.message.reply_text('⚠️ Ошибка. Начни заново через меню.')
        return ConversationHandler.END

    cancel_reminder(context, buyback_id)

    response_data = {}

    if step_type == TaskStep.StepType.PHOTO:
        if not update.message.photo:
            await update.message.reply_text('📸 Отправь фото, пожалуйста')
            schedule_reminder(context, buyback_id, update.effective_chat.id)
            return STEP_RESPONSE

        photo = update.message.photo[-1]
        file = await photo.get_file()
        file_path = f'buybacks/{buyback_id}/step_{step.order}_{photo.file_id}.jpg'

        import os
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        await file.download_to_drive(full_path)

        response_data = {'photo': file_path}

    elif step_type == TaskStep.StepType.ARTICLE_CHECK:
        text = update.message.text.strip()
        correct_article = step.settings.get('correct_article', '')

        if text != correct_article:
            await update.message.reply_text('❌ Артикул не совпадает. Проверь и введи ещё раз.')
            schedule_reminder(context, buyback_id, update.effective_chat.id)
            return STEP_RESPONSE

        response_data = {'value': text}

    elif step_type == TaskStep.StepType.TEXT_MODERATED:
        text = update.message.text
        if len(text) < 10:
            await update.message.reply_text('✏️ Текст слишком короткий. Напиши подробнее.')
            schedule_reminder(context, buyback_id, update.effective_chat.id)
            return STEP_RESPONSE

        response_data = {'text': text}

    elif step_type == TaskStep.StepType.ORDER_NUMBER:
        text = update.message.text.strip()
        response_data = {'value': text}

    # Определяем статус на основе настройки шага
    if step.requires_moderation:
        status = BuybackResponse.Status.PENDING
    else:
        status = BuybackResponse.Status.AUTO_APPROVED

    # Вычисляем дедлайн
    deadline = None
    if step.timeout_hours:
        deadline = timezone.now() + timedelta(hours=step.timeout_hours)

    # Сохраняем ответ
    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data=response_data,
        status=status,
        deadline_at=deadline,
    )

    # Если требует модерации — ждём
    if status == BuybackResponse.Status.PENDING:
        await update.message.reply_text(
            '✅ Принято! Ожидай проверки модератором.',
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # Если авто-одобрено — переходим к следующему шагу
    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def step_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки подтверждения"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])
    cancel_reminder(context, buyback_id)

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'confirmed': True},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def step_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора варианта"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    buyback_id = int(parts[1])
    choice = parts[2]

    cancel_reminder(context, buyback_id)

    try:
        buyback = await Buyback.objects.select_related('task').aget(id=buyback_id)
        step = await buyback.task.steps.filter(order=buyback.current_step).afirst()
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'choice': choice},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    buyback.current_step += 1
    await buyback.asave(update_fields=['current_step'])

    return await show_current_step(update, context, buyback)


async def cancel_buyback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выкупа"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])
    cancel_reminder(context, buyback_id)

    try:
        buyback = await Buyback.objects.aget(id=buyback_id)
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Выкуп не найден')
        return ConversationHandler.END

    if buyback.status not in [Buyback.Status.IN_PROGRESS]:
        await query.edit_message_text('⚠️ Этот выкуп нельзя отменить')
        return ConversationHandler.END

    buyback.status = Buyback.Status.CANCELLED
    await buyback.asave(update_fields=['status'])

    await query.edit_message_text(
        '❌ Выкуп отменён.\n\n'
        'Ты можешь взять другое задание в меню.'
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда отмены"""
    buyback_id = context.user_data.get('buyback_id')
    if buyback_id:
        cancel_reminder(context, buyback_id)

    context.user_data.clear()
    await update.message.reply_text(
        'Действие отменено.',
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END