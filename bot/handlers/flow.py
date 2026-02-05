from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from django.conf import settings
from django.utils import timezone
import os

from account.models import TelegramUser
from catalog.models import Task
from steps.models import TaskStep, StepType
from steps.validators import get_validator
from pipeline.models import Buyback, BuybackResponse
from pipeline.services import format_step_message
from bot.keyboards.reply import main_menu_keyboard


# Состояние ConversationHandler
WAITING_RESPONSE = 1


async def resume_buyback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возобновить активный выкуп (entry point)"""
    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        return None

    buyback = await Buyback.objects.filter(
        user=user,
        status=Buyback.Status.IN_PROGRESS,
    ).select_related('task').order_by('-started_at').afirst()

    if not buyback:
        return None

    step = await TaskStep.objects.filter(
        task_id=buyback.task_id,
        order=buyback.current_step,
    ).afirst()

    if not step:
        return None

    context.user_data['buyback_id'] = buyback.id
    context.user_data['step_id'] = step.id
    context.user_data['step_type'] = step.step_type

    return await handle_response(update, context)


async def take_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Взять задание"""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(':')[1])

    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
        task = await Task.objects.select_related('product').aget(id=task_id, is_active=True)
    except (TelegramUser.DoesNotExist, Task.DoesNotExist):
        await query.edit_message_text('⚠️ Ошибка. Попробуй снова.')
        return ConversationHandler.END

    if user.is_blocked:
        await query.edit_message_text('⛔ Аккаунт заблокирован')
        return ConversationHandler.END

    available = await task.product.aget_quantity_available()
    if available <= 0:
        await query.edit_message_text('⚠️ Товар закончился')
        return ConversationHandler.END

    can_take, limit_msg = await task.product.acheck_user_limit(user)
    if not can_take:
        await query.edit_message_text(f'⚠️ Лимит исчерпан: {limit_msg}')
        return ConversationHandler.END

    has_active = await Buyback.objects.filter(
        task=task,
        user=user,
        status=Buyback.Status.IN_PROGRESS,
    ).aexists()

    if has_active:
        await query.edit_message_text('⚠️ У тебя уже есть активный выкуп этого задания')
        return ConversationHandler.END

    first_step = await task.steps.order_by('order').afirst()
    if not first_step:
        await query.edit_message_text('⚠️ В задании нет шагов')
        return ConversationHandler.END

    buyback = await Buyback.objects.acreate(
        task=task,
        user=user,
        current_step=first_step.order,
    )

    context.user_data['buyback_id'] = buyback.id

    await query.edit_message_text('✅ Задание взято! Загружаю первый шаг...')

    return await show_step(update, context, buyback, first_step)


async def show_step(update: Update, context: ContextTypes.DEFAULT_TYPE, buyback: Buyback, step: TaskStep):
    """Показать шаг пользователю"""
    task = await Task.objects.aget(id=buyback.task_id)
    total_steps = await task.steps.acount()

    text = format_step_message(task, step, total_steps)

    context.user_data['step_id'] = step.id
    context.user_data['step_type'] = step.step_type

    keyboard = get_step_keyboard(step, buyback.id)
    chat_id = update.effective_chat.id

    if step.image:
        with open(step.image.path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                parse_mode='HTML',
                reply_markup=keyboard,
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=keyboard,
        )

    return WAITING_RESPONSE


def get_step_keyboard(step: TaskStep, buyback_id: int):
    """Клавиатура для шага"""
    buttons = []

    if step.step_type == StepType.CONFIRM:
        buttons.append([InlineKeyboardButton('✅ Готово', callback_data=f'confirm:{buyback_id}')])

    elif step.step_type == StepType.CHOICE:
        choices = step.settings.get('choices', [])
        for choice in choices:
            buttons.append([InlineKeyboardButton(choice, callback_data=f'choice:{buyback_id}:{choice}')])

    buttons.append([InlineKeyboardButton('❌ Отменить', callback_data=f'cancel:{buyback_id}')])

    return InlineKeyboardMarkup(buttons)


async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа пользователя (текст/фото)"""
    buyback_id = context.user_data.get('buyback_id')
    step_id = context.user_data.get('step_id')
    step_type = context.user_data.get('step_type')

    if not buyback_id or not step_id:
        try:
            user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
            buyback = await Buyback.objects.filter(
                user=user,
                status=Buyback.Status.IN_PROGRESS,
            ).select_related('task').order_by('-started_at').afirst()

            if buyback:
                step = await TaskStep.objects.filter(
                    task_id=buyback.task_id,
                    order=buyback.current_step,
                ).afirst()

                if step:
                    buyback_id = buyback.id
                    step_id = step.id
                    step_type = step.step_type
                    context.user_data['buyback_id'] = buyback_id
                    context.user_data['step_id'] = step_id
                    context.user_data['step_type'] = step_type
        except TelegramUser.DoesNotExist:
            pass

    if not buyback_id or not step_id:
        return ConversationHandler.END

    try:
        buyback = await Buyback.objects.select_related('task__product').aget(id=buyback_id)
        step = await TaskStep.objects.aget(id=step_id)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        await update.message.reply_text('⚠️ Ошибка. Начни заново.')
        return ConversationHandler.END

    if step_type == StepType.PHOTO:
        if not update.message.photo:
            await update.message.reply_text('📸 Отправь фото')
            return WAITING_RESPONSE

        photo = update.message.photo[-1]
        file = await photo.get_file()
        file_path = f'buybacks/{buyback_id}/step_{step.order}_{photo.file_id}.jpg'
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        await file.download_to_drive(full_path)
        user_input = file_path

    elif step_type == StepType.PAYMENT_DETAILS:
        return await handle_payment_input(update, context, buyback, step)

    else:
        user_input = update.message.text

    validator = get_validator(step, buyback)
    result = await validator.validate(user_input)

    if not result.is_valid:
        await update.message.reply_text(result.error_message)
        return WAITING_RESPONSE

    status = BuybackResponse.Status.PENDING if validator.requires_moderation else BuybackResponse.Status.AUTO_APPROVED

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data=result.data,
        status=status,
    )

    if status == BuybackResponse.Status.PENDING:
        buyback.status = Buyback.Status.ON_MODERATION
        await buyback.asave(update_fields=['status'])

        await update.message.reply_text(
            '✅ Отправлено на проверку! Ожидай.',
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    return await advance_to_next_step(update, context, buyback)


async def handle_payment_input(update: Update, context: ContextTypes.DEFAULT_TYPE, buyback: Buyback, step: TaskStep):
    """Обработка многошагового ввода реквизитов"""
    payment_step = context.user_data.get('payment_step', 'phone')
    text = update.message.text.strip()

    user = await TelegramUser.objects.aget(id=buyback.user_id)

    if payment_step == 'phone':
        user.phone = text
        await user.asave(update_fields=['phone'])
        context.user_data['payment_step'] = 'bank'
        await update.message.reply_text('🏦 Введи название банка (Kaspi, Halyk, Jusan):')
        return WAITING_RESPONSE

    elif payment_step == 'bank':
        user.bank_name = text
        await user.asave(update_fields=['bank_name'])
        context.user_data['payment_step'] = 'name'
        await update.message.reply_text('👤 Введи ФИО как на карте:')
        return WAITING_RESPONSE

    elif payment_step == 'name':
        user.card_holder_name = text
        await user.asave(update_fields=['card_holder_name'])
        context.user_data.pop('payment_step', None)

        await BuybackResponse.objects.acreate(
            buyback=buyback,
            step=step,
            response_data={
                'phone': user.phone,
                'bank_name': user.bank_name,
                'card_holder_name': user.card_holder_name,
            },
            status=BuybackResponse.Status.AUTO_APPROVED,
        )

        return await advance_to_next_step(update, context, buyback)

    return WAITING_RESPONSE


async def advance_to_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE, buyback: Buyback):
    """Переход к следующему шагу"""
    task = await Task.objects.aget(id=buyback.task_id)
    next_step = await task.steps.filter(order__gt=buyback.current_step).order_by('order').afirst()

    if next_step:
        buyback.current_step = next_step.order
        await buyback.asave(update_fields=['current_step'])
        return await show_step(update, context, buyback, next_step)

    buyback.status = Buyback.Status.PENDING_REVIEW
    buyback.completed_at = timezone.now()
    await buyback.asave(update_fields=['status', 'completed_at'])

    text = (
        '🎉 <b>Все шаги выполнены!</b>\n\n'
        'Твой выкуп отправлен на проверку.'
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Выбери действие:',
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_menu_keyboard())

    context.user_data.clear()
    return ConversationHandler.END


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка подтверждения"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])

    try:
        buyback = await Buyback.objects.aget(id=buyback_id)
        step = await TaskStep.objects.aget(task_id=buyback.task_id, order=buyback.current_step)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    context.user_data['buyback_id'] = buyback.id

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'confirmed': True},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    await query.edit_message_text('✅ Подтверждено!')

    return await advance_to_next_step(update, context, buyback)


async def choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка выбора варианта"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    buyback_id = int(parts[1])
    choice = parts[2]

    try:
        buyback = await Buyback.objects.aget(id=buyback_id)
        step = await TaskStep.objects.aget(task_id=buyback.task_id, order=buyback.current_step)
    except (Buyback.DoesNotExist, TaskStep.DoesNotExist):
        await query.edit_message_text('⚠️ Ошибка')
        return ConversationHandler.END

    context.user_data['buyback_id'] = buyback.id

    await BuybackResponse.objects.acreate(
        buyback=buyback,
        step=step,
        response_data={'choice': choice},
        status=BuybackResponse.Status.AUTO_APPROVED,
    )

    await query.edit_message_text(f'✅ Выбрано: {choice}')

    return await advance_to_next_step(update, context, buyback)


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выкупа"""
    query = update.callback_query
    await query.answer()

    buyback_id = int(query.data.split(':')[1])

    try:
        buyback = await Buyback.objects.aget(id=buyback_id)
    except Buyback.DoesNotExist:
        await query.edit_message_text('⚠️ Выкуп не найден')
        return ConversationHandler.END

    buyback.status = Buyback.Status.CANCELLED
    await buyback.asave(update_fields=['status'])

    await query.edit_message_text('❌ Выкуп отменён')

    context.user_data.clear()
    return ConversationHandler.END