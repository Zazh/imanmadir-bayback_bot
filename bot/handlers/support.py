from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from account.models import TelegramUser
from support.models import Ticket, Message
from bot.keyboards.reply import main_menu_keyboard


# Состояние
WAITING_MESSAGE = 1


async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка Поддержка"""
    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Нажми /start')
        return ConversationHandler.END

    # Ищем открытый тикет или создаём новый
    ticket = await Ticket.objects.filter(
        user=user,
        status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS],
    ).order_by('-created_at').afirst()

    if not ticket:
        ticket = await Ticket.objects.acreate(
            user=user,
            ticket_type=Ticket.Type.GENERAL,
            subject='Обращение в поддержку',
        )

    context.user_data['ticket_id'] = ticket.id

    # Показываем последние сообщения
    messages = []
    async for msg in ticket.messages.order_by('-created_at')[:5]:
        messages.append(msg)
    messages.reverse()

    if messages:
        text = '💬 <b>Чат с поддержкой</b>\n\n'
        for msg in messages:
            if msg.sender_type == Message.SenderType.USER:
                text += f'👤 Ты: {msg.text}\n\n'
            elif msg.sender_type == Message.SenderType.MANAGER:
                text += f'👨‍💼 Поддержка: {msg.text}\n\n'
            else:
                text += f'🤖 {msg.text}\n\n'
        text += '—\nНапиши сообщение:'
    else:
        text = (
            '💬 <b>Чат с поддержкой</b>\n\n'
            'Напиши свой вопрос, и менеджер ответит в ближайшее время.'
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('❌ Закрыть чат', callback_data='support_close')],
    ])

    await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

    return WAITING_MESSAGE


async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение сообщения от пользователя"""
    ticket_id = context.user_data.get('ticket_id')

    if not ticket_id:
        await update.message.reply_text(
            '⚠️ Сессия истекла. Нажми "💬 Поддержка" снова.',
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    try:
        ticket = await Ticket.objects.aget(id=ticket_id)
    except Ticket.DoesNotExist:
        await update.message.reply_text('⚠️ Ошибка', reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    # Сохраняем сообщение
    text = update.message.text

    await Message.objects.acreate(
        ticket=ticket,
        sender_type=Message.SenderType.USER,
        text=text,
    )

    # Обновляем статус тикета
    if ticket.status == Ticket.Status.OPEN:
        ticket.status = Ticket.Status.IN_PROGRESS
        await ticket.asave(update_fields=['status'])

    await update.message.reply_text(
        '✅ Сообщение отправлено!\n\n'
        'Ожидай ответа от менеджера. Можешь написать ещё.',
    )

    return WAITING_MESSAGE


async def support_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть чат с поддержкой"""
    query = update.callback_query
    await query.answer()

    context.user_data.pop('ticket_id', None)

    await query.edit_message_text('💬 Чат закрыт. Если понадобится помощь — пиши!')

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выбери действие:',
        reply_markup=main_menu_keyboard(),
    )

    return ConversationHandler.END


async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из чата поддержки"""
    context.user_data.pop('ticket_id', None)
    await update.message.reply_text('Выбери действие:', reply_markup=main_menu_keyboard())
    return ConversationHandler.END