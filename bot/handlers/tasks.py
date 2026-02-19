from telegram import Update
from telegram.ext import ContextTypes

from account.models import TelegramUser
from catalog.models import Task
from bot.keyboards.inline import tasks_list_keyboard, task_detail_keyboard


async def tasks_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список доступных заданий"""
    try:
        user = await TelegramUser.objects.aget(telegram_id=update.effective_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text('⚠️ Нажми /start')
        return

    if user.is_blocked:
        await update.message.reply_text('⛔ Аккаунт заблокирован')
        return

    tasks = []
    async for task in Task.objects.filter(
        is_active=True,
        product__is_active=True,
    ).select_related('product'):
        # Проверяем есть ли товар
        available = await task.product.aget_quantity_available()
        if available > 0:
            tasks.append(task)

    if not tasks:
        await update.message.reply_text(
            '📋 <b>Задания</b>\n\n'
            'Сейчас нет доступных заданий. Загляни позже!',
            parse_mode='HTML'
        )
        return

    await update.message.reply_text(
        '📋 <b>Доступные задания</b>\n\n'
        'Выбери задание:',
        parse_mode='HTML',
        reply_markup=tasks_list_keyboard(tasks),
    )


async def task_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали задания"""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(':')[1])

    try:
        task = await Task.objects.select_related('product').aget(id=task_id)
    except Task.DoesNotExist:
        await query.edit_message_text('⚠️ Задание не найдено')
        return

    # Считаем шаги
    steps_count = await task.steps.acount()

    # Доступное количество
    available = await task.product.aget_quantity_available()

    text = (
        f'📦 <b>{task.title}</b>\n\n'
        f'🏷 Товар: {task.product.name}\n'
        f'💰 Цена: {task.product.price}₽\n'
        f'💵 Выплата: <b>{task.payout}₽</b>\n\n'
        f'📝 Шагов: {steps_count}\n'
        f'📊 Осталось: {available} шт.\n'
        f'👤 Лимит: {task.product.get_limit_display()}'
    )

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=task_detail_keyboard(task.id, available > 0),
    )


async def tasks_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку заданий"""
    query = update.callback_query
    await query.answer()

    tasks = []
    async for task in Task.objects.filter(
        is_active=True,
        product__is_active=True,
    ).select_related('product'):
        available = task.product.quantity_total - task.product.quantity_completed
        if available > 0:
            tasks.append(task)

    if not tasks:
        await query.edit_message_text(
            '📋 <b>Задания</b>\n\nНет доступных заданий.',
            parse_mode='HTML'
        )
        return

    await query.edit_message_text(
        '📋 <b>Доступные задания</b>\n\nВыбери задание:',
        parse_mode='HTML',
        reply_markup=tasks_list_keyboard(tasks),
    )